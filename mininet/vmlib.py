import libvirt
import sys, os, subprocess, shutil
from xml.etree import ElementTree as etree


vms = {}
respath = '../virtual/res/'
vmspath = '../virtual/vms/'
mountpath = '/mnt/alpine/'


def destroy(hostname):
  conn = getLibvirtConn()
  target = conn.lookupByName(hostname)
  if target == None:
    print('Error: Host not found')
    conn.close()
    return False
  else:
    target.shutdown()
    return True


def getMAC(hostname):
  conn = getLibvirtConn()
  target = lookupByName(hostname)
  if target == None:
    print('Error: Target VM not found')
    return False
  raw_XML = target.XMLDesc(0)
  conn.close()
  xml = ET.parse(raw_XML)
  root = xml.getroot()
  return root.find('mac').get('address')


def getLibvirtConn():
  ''' Currently, assumes libvirtd is unsecured
  '''
  try:
    conn = libvirt.open('xen+tcp:///')
    return conn
  except:
    print('Failed to acquire connection to xen')
    sys.exit(1)


def generateXML(hostname, vmemory=2048, vcpu=1, os_name=alpine):
  kernel = mountpath + 'boot/vmlinuz-virt'
  initrd = mountpath + 'boot/initramfs-virt'
  pvgrub = '/usr/lib/grub-xen/grub-x86_64-xen.bin'

  #print(ET.tostring(ET.parse('../libxml/defaultsetup.xml').getroot()))
  defaultxml = ET.parse(respath + '/defaultsetup.xml')
  tree = defaultxml.getroot()
  tree.find('name').text = hostname
  tree.find('os/type').text = 'linux'
  tree.find('os/kernel').text = pvgrub
  #tree.find('os/boot').set('dev', 'hd')
  tree.find('memory').text = vmemory
  tree.find('vcpu').text = vcpu
  devices = tree.find('devices')
  disk1 = ET.SubElement(devices, 'disk')
  disk1.set('type', 'file')
  disk1.set('device', 'disk')
  disksrc = ET.SubElement(disk1, 'source')
  disksrc.set('file', createVMDisk(hostname, os_name))
  disk1target = ET.SubElement(disk1, 'target')
  disk1target.set('dev', 'xvda')
  defaultxml.write(f"{vmspath}{vmname}/{vmname}.xml")


def createVMNode(hostname, vmemory, vcpu=1, os_name="alpine"):
  os.mkdir(vmpath + os_name)
  generateXML(hostname, vmemory, vcpu, os_name)
  createVMDisk(hostname, os_name)
  conn.getLibvirtConn()
  conn.createXML(respath+'/defaultsetup.xml', 0)
  conn.close()


def createVMDisk(hostname, os_name):
  disk = f"{vmspath}{vmname}/{vmname}.img"
  diskpath = os.path.abspath(disk)
  if os_name == 'alpine':
    shutil.copyfile(respath + 'disks/alpine-base.img', diskpath)
    return diskpath

