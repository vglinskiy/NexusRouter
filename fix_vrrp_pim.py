#!/bin/env python
import sys
import json
from NexusRouter import NexusRouter
import argparse

def main():
  show_vrrp_backup = "show vrrp backup"
  fix_commands = [" ", "ip pim dr-priority 150", "vrrp 100", "preempt"]
  parser = argparse.ArgumentParser()
  parser.add_argument("device_name", help="router name", metavar=('<router name>') )  

  args = parser.parse_args()
  myrouter=NexusRouter(args.device_name)
  myrouter.connect()
  try:
    vrrp_backup_intf = myrouter.show_command(show_vrrp_backup)["TABLE_vrrp_group"]
  except Exception as err:
    print err
    sys.exit(1)

  if type(vrrp_backup_intf) is dict:
    # If there is only 1 element, Cisco's API returns dict 
    # instead of list of dicts
    vrrp_backup_intf = [vrrp_backup_intf]
 
  for vrrp_intf in vrrp_backup_intf:
    fix_commands[0] = "interface "+vrrp_intf["ROW_vrrp_group"]["sh_if_index"]
    print "Updating interface {0}".format(vrrp_intf["ROW_vrrp_group"]["sh_if_index"])
    try:
      myrouter.conf_command(fix_commands)
    except Exception as err:
      print err
      sys.exit(1)
  myrouter.save_config() 

if __name__ == '__main__':
  main()
