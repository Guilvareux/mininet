import libvirt
import sys, os, subprocess, shutil
from xml.etree import ElementTree as etree


vms = {}
respath = '../virtual/res/'
vmspath = '../virtual/vms/'

interfaceXML = """
<interface>
</interface>
"""

#destroy VM
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

#Get MAC address from domainxml dump
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


#Get Libvirt connection - Currently assumes libvirtd is insecure 'xen+tcp'
def getLibvirtConn():
  try:
    conn = libvirt.open('xen+tcp:///')
    return conn
  except:
    print('Failed to acquire connection to xen')
    sys.exit(1)


#Create domain xml
def generateXML(hostname, vmemory=2048, vcpu=1, os_name=alpine, disk=None):
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
  if disk == None:
    disksrc.set('file', createVMDisk(hostname, os_name))
  else:
    docksrc.set('file', disk)
    
  disk1target = ET.SubElement(disk1, 'target')
  disk1target.set('dev', 'xvda')
  defaultxml.write(f"{vmspath}{vmname}/{vmname}.xml")


#Create disk and boot domain
def createVMNode(hostname, vmemory, vcpu=1, os_name="alpine"):
  os.mkdir(vmpath + os_name)
  generateXML(hostname, vmemory, vcpu, os_name)
  createVMDisk(hostname, os_name)
  conn.getLibvirtConn()
  guest = conn.createXML(respath+'/defaultsetup.xml', 0)
  if guest != None:
    if hostname not in vms:
      vms[hostname] = "Node"
    else:
      print('Node already exists in dict')
  conn.close()


#Copy base image and run 
def createVMDisk(hostname, os_name):
  disk = f"{vmspath}{vmname}/{vmname}.img"
  diskpath = os.path.abspath(disk)
  if os_name == 'alpine':
    shutil.copyfile(respath + 'disks/alpine-base.img', diskpath)
    return diskpath


#Update a device on a running domain.
def updateDevice(hostname):
  #Add xml parse
  xml = ''
  conn = getLibvirtConn()
  target = conn.lookupByName(hostname)
  if target == None:
    print('Error: Host not found')
    conn.close()
    return False
  else:
    target.updateDeviceFlags(xml)
    return True
  conn.close()

#Create domainxml to update an interface on a live running vm
def updateInterface(hostname, name, inttype, mac=None, ip=None, source):
  base = ET.parse(interfaceXML)
  tree = base.getroot()
  if name:
    tree.set('name', name)
  if inttype:
    tree.set('type', inttype)
  if mac != None:
    xmlmac = ET.SubElement(tree, 'mac')
    xmlmac.set('address', mac)
  if source:
    xmlsource = ET.SubElement(tree, 'source')

  updateDevice(hostname)