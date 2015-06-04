#!/usr/bin/python

"""
fakecluster.py: a fake cluster for testing Mininet cluster edition!!!

We are going to self-host Mininet by creating a virtual cluster
for cluster edition.

Note: ssh is kind of a mess - you end up having to do things
like h1 sudo -E -u openflow ssh 10.2
"""

from mininet.net import Mininet
from mininet.node import Host
from mininet.cli import CLI
from mininet.topo import Topo, SingleSwitchTopo
from mininet.log import setLogLevel, warn
from mininet.util import errRun, quietRun
from mininet.link import Link

from functools import partial
from tempfile import NamedTemporaryFile


"""
Comments
Next:
- dnsmasq on m1
- custom /etc/resolv.conf pointing to m1 on m1-mn
And maybe:
- dnsmasq on root server
- root resolv.conf pointing to dnsmasq? Hmm...
Also:
- cleanup shouldn't kill *everything* if we're in a namespace
- pid namespace would fix this
"""

class Server( Host ):
    "A host that supports overlay directories"

    def __init__( self, *args, **kwargs ):
        """overlayDirs: ['/mountpoint',...] or [('/mountpoint', '/overlay')...]
           If '/overlay' is present and non-empty, use it as a persistent directory.
           otherwise use a tmpfs."""
        self.overlayDirs = kwargs.pop( 'overlayDirs', () )
        Host.__init__( self, *args, **kwargs )

    def mountPrivateDirs( self ):
        """Overridden to pre-mount overlay dirs
           Usually there isn't a good reason for them to overlap,
           but if they do, then the private dirs are mounted
           on top of the overlay dirs.
           We also make our private dirs root/755"""
        self.mountOverlayDirs()
        super( Server, self ).mountPrivateDirs()

    def unmountPrivateDirs( self ):
        "Overridden to also unmount overlay dirs"
        super( Server, self).unmountPrivateDirs()
        self.unmountOverlayDirs()

    def _overlayFrom( self, entry ):
        "Helper function: return mountpaint, overlay, tmpfs from entry"
        if type( entry ) is str:
            # '/mountpoint'
            mountpoint, overlay = entry, None
        elif len( entry ) is 1:
            # [ '/mountpoint' ]
            mountpoint, overlay = entry[ 0 ], None
        else:
            # [ '/mountpoint', '/overlay' ]
            mountpoint, overlay = entry
        tmpfs = None if overlay else '/tmp/%s/%s' % ( self, mountpoint )
        return mountpoint, overlay, tmpfs

    def mountOverlayDirs( self ):
        """Mount overlay directories. Overlay directories are similar
           to private directories except they are copy-on-write copies
           of directories in the host file system.
           overlayDirs is of the form ((mountpoint,overlaydir), ...)
           much like privateDirs. If overlaydir doesn't exist, we
           mount a tmpfs at the specified mount point."""
        # Avoid expanding a string into a list of chars
        assert not isinstance( self.overlayDirs, basestring )
        for entry in self.overlayDirs:
            mountpoint, overlay, tmpfs  = self._overlayFrom( entry )
            # Create tmpfs if overlay dir is not specified
            if not overlay:
                overlay = tmpfs
                self.cmd( 'mkdir -p', overlay )
                self.cmd( 'mount -t tmpfs tmpfs', overlay )
            # Mount overlay dir at mount point
            self.cmd( ( 'mount -t overlayfs -o upperdir=%s,lowerdir=%s'
                        ' overlayfs %s' ) % ( overlay, mountpoint, mountpoint ) )

    def unmountOverlayDirs( self ):
        "Unmount overlay directories"
        for entry in self.overlayDirs:
            mountpoint, overlay, tmpfs = self._overlayFrom( entry )
            # Unfortunately these umounts can fail if the mount point
            # is in use, possibly leaving tmpfs garbage in the root
            # mount namespace / file system
            self.cmd( 'umount', mountpoint )
            if not overlay:
                self.cmd( 'umount', tmpfs )


class MininetServer( Server ):
    "A server (for nested Mininet) that can run ssh and ovsdb"

    inNamespace =  [ 'net', 'mnt', 'pid', 'uts' ]
    overlayDirs = [ '/etc', '/var/run', '/var/log' ]
    privateDirs = [ '/var/run/sshd', '/etc/openvswitch',
                    '/var/run/openvswitch', '/var/log/openvswitch' ]

    def __init__( self, *args, **kwargs ):
        "Add overlay dirs and private dirs, and change permissions"
        kwargs.update( inNamespace = self.inNamespace,
                       overlayDirs=self.overlayDirs,
                       privateDirs=self.privateDirs )
        super( Server, self ).__init__( *args, **kwargs )
        # Change permissions, mainly for ssh
        for pdir in self.privateDirs:
            self.cmd( 'chown root:root', pdir )
            self.cmd( 'chmod 755', pdir )

    @staticmethod
    def whatever( x, y='foo' ):
        "what the heck?!?!?!"
        print x, y

    @staticmethod
    def updateHostsFiles( servers, tmpdir='/tmp' ):
        """Update local hosts files on a list of servers
           servers: list of servers
           tmpdir: tmp dir shared between mn and servers"""
        # This scales as n^2, so for a large configuration it's
        # more efficient to use a DNS server
        for s in servers:
            dirs = getattr( s, 'overlayDirs', [] ) + getattr( s, 'privateDirs', [] )
            if '/etc' in dirs:
                with NamedTemporaryFile( dir=tmpdir ) as tmpfile:
                    tmpfile.write( '# Mininet hosts file\n' )
                    tmpfile.write( '127.0.0.1 localhost %s\n' % s )
                    for t in servers:
                        tmpfile.write( '%s %s\n' % ( t.IP(), t ) )
                    tmpfile.flush()
                    s.cmd( 'cp', tmpfile.name, '/etc/hosts' )
            else:
                warn( 'not updating hosts file on %s\n' % s )

    def service( self, cmd ):
        """Start or stop a service
           usage: service( 'ssh stop' )"""
        self.cmd( '/etc/init.d/%s' % cmd )

    def motd( self ):
        "Return login message as a string"
        return 'Welcome to Mininet host %s at %s' % ( self, self.IP() )

    def startSSH( self, motdPath='/var/run/motd.dynamic' ):
        "Update motd, clear out utmp/wtmp/btmp, and start sshd"
        # Note: /var/run and /var/log must be overlays!
        self.cmd( "echo  '%s' > %s" % ( self.motd(), motdPath ) )
        self.cmd( 'truncate -s0 /var/run/utmp /var/log/wtmp* /var/log/btmp*' )
        # sshd.pid should really be in /var/run/sshd instead of /var/run
        self.cmd( 'rm /var/run/sshd.pid' )
        self.cmd( '/etc/init.d/ssh start' )

    def config( self, ssh=False, ovs=False, **kwargs ):
        """Configure/start sshd and other stuff
           ssh: start sshd?
           ovs: start Open vSwitch?"""
        self.ssh, self.ovs = ssh, ovs
        super( MininetServer, self ).config( self, **kwargs )
        if self.ssh:
            self.startSSH()
        if self.ovs:
            self.service( 'openvswitch-switch start' )
        if 'uts' in self.inNamespace:
            self.cmd( 'hostname', self )

    def terminate( self, *args, **kwargs ):
        "Shut down services and terminate server"
        if self.ssh:
            self.service( 'ssh stop' )
        if self.ovs:
            self.service( 'openvswitch-switch stop' )
        super( MininetServer, self ).terminate( *args, **kwargs )


class ServerLink( Link ):
    def intfName( self, node, n ):
        "Override to avoid destruction by cleanup!"
        # This is kind of ugly... for some reason 'eth0' fails so
        # we just use 'm1eth0'; however, this should nest reasonably.
        return ( node.name + 'eth' + repr( n ) if isinstance( node, Server )
                 else node.name + '-eth' + repr( n ) )
    def makeIntfPair( self, *args, **kwargs ):
        "Override to use quietRun"
        kwargs.update( runCmd=quietRun )
        super( ServerLink, self ).makeIntfPair( *args, **kwargs )

class ClusterTopo( Topo ):
    "Cluster topology: m1..mN"
    def build( self, n ):
        ms1 = self.addSwitch( 'ms1' )
        for i in range( 1, n + 1 ):
            h = self.addHost( 'm%d' % i )
            self.addLink( h, ms1, cls=ServerLink )


def test():
    "Test this setup"
    setLogLevel( 'info' )
    topo = ClusterTopo( 3 )
    host = partial( MininetServer, ssh=True, ovs=True )
    net = Mininet( topo=topo, host=host, ipBase='10.0/24' )
    MininetServer.updateHostsFiles( net.hosts )
    # addNAT().configDefault() also connects root namespace to Mininet
    net.addNAT().configDefault()
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    test()