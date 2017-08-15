#!/usr/local/bin/python2.7.10    
import re                        
import os                        
import sys                       
import json                      
import time                      
import requests                  
import getpass                   
import argparse
from NexusRouter import NexusRouter

class NexusDivertTraffic(NexusRouter):
  def __init__(self, device_name, resume):
    NexusRouter.__init__(self, device_name)
    self.device_name = device_name
    self.resume = resume

  def ospf_updown(self):
    """ set/remove max-metric for router's LSAs
    """
    _ospf_show_command="show ip ospf"
    if self.resume:
       _ospf_config_command=["router ospf", "no max-metric router-lsa"]
       _ospf_msg="Removing max metric for router's LSAs"
    else:
       _ospf_config_command=["router ospf", "max-metric router-lsa"]
       _ospf_msg="Setting max metric for router's LSAs"
    try:
      _ospf_output=self.show_command(_ospf_show_command)
    except Exception as err:
      print err
    _ospf_tag=_ospf_output["TABLE_ctx"]["ROW_ctx"]["ptag"]
    _ospf_config_command[0]="router ospf "+str(_ospf_tag)
    print _ospf_msg
    try:
      self.conf_command(_ospf_config_command)
    except Exception as err:
      print err
    time.sleep(5) 

  def bgp_updown(self):
    """shut/unshut BGP router                        
    """  
    _bgp_show_command="show bgp sessions"
    if self.resume:
       _bgp_config_command=["router bgp", "no shutdown"]
       _bgp_msg="Re-enabling BGP router"
    else:
       _bgp_config_command=["router bgp", "shutdown"]
       _bgp_msg="Shutting down BGP router"
    _local_as=self.show_command(_bgp_show_command)["localas"]
    _bgp_config_command[0]="router bgp "+str(_local_as)
    print _bgp_msg
    try:
      self.conf_command(_bgp_config_command)
    except Exception as err:
      print err
    if self.resume:
      print "BGP protocol is up\n"                                                                                                   
      print "Now checking if BGP peerings are Established"                                                                           
      _attempt = 1                                                                                                                    
      while _attempt <= 4:                                                                                                            
        _bgp_state = 1                                                                                                                
        _bgp_peers=self.show_command(_bgp_show_command)['TABLE_vrf']['ROW_vrf']['TABLE_neighbor']['ROW_neighbor']
        for _bgp_nbr in _bgp_peers:                                                                                                    
          if _bgp_nbr['state'] != 'Established':                                                                                      
            _bgp_state = 0                                                                                                            
            print "At least one BGP session is not Established. I'll wait 10 seconds and try again\n"                                
            time.sleep(10)                                                                                                           
            break
        _attempt += 1                                                                                                                 
        if _bgp_state == 1:                                                                                                           
          print "All BGP sessions are Established.\n"                                                                                
          print "Waiting 10 seconds to give BGP chance to converge"                                                                  
          time.sleep(10) # Giving time BGP to converge                                                                               
          break                                                                                                                      
      if _bgp_state == 0:                                                                                                             
          # after all this waiting some BGP sessions are still down                                                                    
          print "At least one BGP session is still not Established. Log into {0} and troubleshoot\n".format(self.router)               
          sys.exit()

  def pim_vrrp_updown(self):
    """ changes VRRP and PIM DR priority to divert or restore traffic
        In our model, VRRP master is also PIM DR. Instead of doing multiple
        runs I'll do PIM DR and VRRP mastership change in one shot                                                             
    """
    print "Changing PIM DR and VRRP priority on {0}".format(self.device_name)
    _pim_vrrp_config_template=["interface ","ip pim dr-priority ", "vrrp ", "priority "]
    try:
      _vrrp_interfaces=self.show_command("show vrrp")["TABLE_vrrp_group"]
    except Exception as err:
      print err
      return
    if type(_vrrp_interfaces) == dict:
      # If there is only one VRRP interface, NXAPI returns dict instead of list of dict.
      _vrrp_interfaces=[_vrrp_interfaces]
    for _entry in _vrrp_interfaces:
      _pim_vrrp_config_command=[]
      time.sleep(5)
      if self.resume:
        if _entry["ROW_vrrp_group"]["sh_priority"] == 10:
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[0]+_entry["ROW_vrrp_group"]["sh_if_index"])
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[1]+str(250))
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[2]+str(_entry["ROW_vrrp_group"]["sh_group_id"]))
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[3]+str(250))
          print "Restoring VRRP and PIM DR priority on {0}\n".format(_entry["ROW_vrrp_group"]["sh_if_index"])
      else:
        if _entry["ROW_vrrp_group"]["sh_group_state"] == "Master":
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[0]+_entry["ROW_vrrp_group"]["sh_if_index"])
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[1]+str(10))
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[2]+str(_entry["ROW_vrrp_group"]["sh_group_id"]))
          _pim_vrrp_config_command.append(_pim_vrrp_config_template[3]+str(10))
          print "Lowering VRRP and PIM DR priority on {0}\n".format(_entry["ROW_vrrp_group"]["sh_if_index"])
      try:
        self.conf_command(_pim_vrrp_config_command)
      except Exception as err:
        print err
        pass

def main():
  parser=argparse.ArgumentParser(description="Add/remove router from traffic path")                                                  
  parser.add_argument('device_name', help='name of the router')                                                                      
  parser.add_argument('-r','--resume', action='store_true', default=False, dest='resume',\
                     help='resume traffic through the router')  
  args=parser.parse_args()
  myrouter=NexusDivertTraffic(args.device_name, args.resume)
  if args.resume:
    proceed=raw_input(args.device_name+" will be put back in production. Proceed? [y/n]: ")
    if re.match("Y|y", proceed):
      try:
        myrouter.connect()
      except Exception as err:
        print err
        sys.exit(1)
      myrouter.ospf_updown()
      myrouter.bgp_updown()
      myrouter.pim_vrrp_updown() 
    else:
      print "Exiting..."
      sys.exit(1)
  else:
    proceed=raw_input(args.device_name+" will be removed from traffic path. Proceed? [y/n]: ")
    if re.match("Y|y", proceed):
      try:
        myrouter.connect()
      except Exception as err:
        print err
        sys.exit(1)
      myrouter.pim_vrrp_updown() 
      myrouter.ospf_updown()
      myrouter.bgp_updown()
    else:
      print "Exiting..."
      sys.exit(1)
  myrouter.save_config() 

if __name__ == "__main__":
  main()                                                                           
