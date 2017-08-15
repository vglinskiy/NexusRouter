#!/usr/bin/env python
import re         
import sys        
import json       
import yaml       
import time       
import requests 
import getpass
import argparse
from NexusRouter import NexusRouter

def snap(rname, snapname, playbook):
  ''' collect output of show commands as specified in playbook
  '''
  state={}
  nxrouter=NexusRouter(rname)
  nxrouter.connect()
  for check in playbook.keys():
    snap_output=[]
    try:
      print "Collecting data for \"{0}\"".format(playbook[check]["description"])
      output=nxrouter.show_command(playbook[check]['command'])
    except Exception as err:
      print "Could not collect data for playbook check {0}. ".format(check)+str(err)+". Skipping.\n"
      continue
		# walking down jsonpath to get to the data
    if re.search('/', playbook[check]['jsonpath']):
      jsonpath=playbook[check]['jsonpath'].split("/")
      for idx in jsonpath:
        if output[idx] is None:
          print "\nJSON output for {0} is empty, feature is not configured or jsonpath is incorrect".format(check)
          continue
        else:
        #output=output.get(idx, output)
          output=output.get(idx)
    else:
      output=output[playbook[check]['jsonpath']]
		# end of walk
    if type(output) is not list and type(output) is not dict:
      print "Please check jsonpath parameter for {0} in your playbook.\nIt should point to list\
 of dictionaries or a dictionary. Skipping {0}\n".format(check)
      print type(output)
      print output,"\n"
      continue
    if type(output) is dict:
      #Cisco sucks at this. When there is only one VRRP group or one BGP neighbor they put it directly into dict instead of list of dict
      output=[output]
    if type(output) is list:
      for idx in output:
        if type(idx) is dict:
          temp_snap={}
          for myitem in playbook[check]['items']:
            if re.search('/', myitem):
              ''' Handle dict of dict like one below here. That's why items in playbook have /, like ROW_vrrp_group/sh_if_index
				    	{
	              "ROW_vrrp_group": {
	                "sh_if_index": "port-channel7.1105",
	                "sh_group_id": 100,
	                "sh_group_type": "IPV4",
	                "sh_group_state": "Init",
	                "sh_group_preempt": "Enable",
	                "sh_vip_addr": "10.122.71.1",
	                "sh_priority": 250,
	                "sh_adv_interval": 1
	              }
	            }
              '''
              split_myitem=myitem.split("/")
              if len(split_myitem) !=2:
                print "Dictionary of dictionaries should not be more than 1 level deep, i.e. no more than one \"/\" in items.\
                         Please check {0} in {1} section of the playbook".format(myitem, check)
                continue
              # If multiple items in the same check have / in the name, we do not want to overwrite temp_snap
              if len(temp_snap) == 0:
                temp_snap={split_myitem[0]:{}}
              idx=idx.get(split_myitem[0], idx)
              temp_snap[split_myitem[0]].update({split_myitem[1]:idx[split_myitem[1]]})
             
            else:
              temp_snap[myitem]=idx[myitem]
	            # Handle simple dict like one below here
			        #	{
              #     "chassis_type": 7,
	            #     "chassis_id": "dnjr-lab-cs4b",
       	      #     "l_port_id": 0,
              #     "ttl": 120,
              #     "capability": 1310740,
	            #     "port_type": 5,
	            #     "port_id": "Ethernet1/49",
	            #     "mgmt_addr_type": 0,
	            #     "mgmt_addr": "mgmt_addr"
	            #    }
          snap_output.append(temp_snap)
        else:
          print "I do not know how to handle {0}.\n\n Skipping.\n".format(idx) 
          continue
    state[check]=snap_output

  with open("".join([rname,'-',snapname,'.json']), 'w') as fh2:
    json.dump(state, fh2, indent=2)
    fh2.close()


def check(rname, snapshot, show_passed, playbook):
  ''' Here we will compare pre and post snapshots 
  '''
  try:
    pre_fh=open(rname+"-"+snapshot[0]+".json", "r") 
  except Exception as err:
    print "Can not open {0} snapshot"+str(err).format(snapshot[0])
    sys.exit(1)
  try:
    post_fh=open(rname+"-"+snapshot[1]+".json", "r") 
  except Exception as err:
    print "Can not open {0} snapshot"+str(err).format(snapshot[1])
    sys.exit(1)

  try:
    pre_snap=json.load(pre_fh)
  except Exception as err:
    print "snapshot {0}: ".format(snapshot[0]), err
    pre_fh.close()
    post_fh.close()
    sys.exit(1)

  try:
    post_snap=json.load(post_fh)
  except Exception as err:
    print "snapshot {0}: ".format(snapshot[1]), err
    pre_fh.close()
    post_fh.close()
    sys.exit(1)

  pre_fh.close()
  post_fh.close()
  for check in playbook.keys():
    check_passed = 1
    if check not in pre_snap.keys() or check not in post_snap.keys():
      print "Test case {0} is not in either {1} or {2} snapshot. Exiting".format(check, snapshot[0], snapshot[1])
      sys.exit(1)
    # see if number of elements in each check matches in both snapshots
    if len(pre_snap[check]) != len(post_snap[check]):   #something is missing in either pre or post snapshots, like bgp neighbor or ospf interface
      for element in pre_snap[check]:         #looking for what's missing
        if element not in post_snap[check]:
          #this element from pre snap is missing in post snap. 
          if re.search('/',playbook[check]["attr"]):
            element=element.get(playbook[check]["attr"].split("/")[0], element)
          msg_str=""
          for i in element.items():
            msg_str=msg_str+str(i[0])+":"+str(i[1])+","
          print "\nFAILED: \"{0:<30}\" \"{1}\" is missing in {2} snapshot".format(playbook[check]["description"], msg_str.rstrip(","), snapshot[1])
          check_passed = 0
    for post_idx in post_snap[check]:
      for pre_idx in pre_snap[check]:
        if re.search('/',playbook[check]["attr"]):
          #attr like ROW_vrrp_group/sh_if_index
          attr_prefix, attr=playbook[check]["attr"].split("/")
          post_idx=post_idx.get(attr_prefix, post_idx)
          pre_idx=pre_idx.get(attr_prefix, pre_idx)
        else:
          attr=playbook[check]["attr"]
        if attr in pre_idx.keys() and post_idx[attr] == pre_idx[attr]:
          pre_set=set(pre_idx.items())
          post_set=set(post_idx.items())
          common_set=pre_set & post_set # what's the same in pre and post
          new_state=post_set.difference(pre_set) # what's different in post snapshot 
          old_state=pre_set.difference(post_set) # what's different in pre snapshot
          if post_idx == pre_idx:
            msg_str=""
            for i in common_set:
              if str(i[0]) != str(attr):
                msg_str=msg_str+str(i[0])+":"+str(i[1])+","
            if show_passed is True:
              print "\nPASSED: \"{0:<30}\" \"{1}\" \"{2}\"".format(playbook[check]["description"], post_idx[attr], msg_str.rstrip(","))
          else:
            msg_str_post=""
            msg_str_pre=""
            for i in new_state:
              msg_str_post=msg_str_post+str(i[0])+":"+str(i[1])+","  
            for i in old_state:
              msg_str_pre=msg_str_pre+str(i[0])+":"+str(i[1])+","
            print "\nFAILED: \"{0:<30}\" \"{1}\" new state: \"{2}\"{3} old state: \"{4}\"\n".format(playbook[check]["description"], post_idx[attr], msg_str_post.rstrip(","), " ", msg_str_pre.rstrip(","))
            check_passed = 0
            
    if check_passed:
      print "CHECK {0:<40} PASSED".format(playbook[check]["description"])      
        

def main():
  parser = argparse.ArgumentParser(usage=sys.argv[0]+" [-h] [--snap <snapshot name>] | [--check pre post] [--show-passed] -f|--file <playbook file> <router name>")
  x_group = parser.add_mutually_exclusive_group()
  x_group.add_argument("--check", help="compare two snapshots", nargs=2, dest="check", metavar=('pre', 'post'))
  x_group.add_argument( "--snap", help="take current state snapshot", nargs=1, dest="snap", metavar=('snapshot'))

  parser.add_argument("device_name", help="router name", metavar=('<router name>') )
  parser.add_argument("-f", "--file", help="playbook file", dest="pfile", required=True, metavar=('<file name>'))
  parser.add_argument("--show-passed", help="show passed checks too when comparing pre and post snapshots", action='store_true', dest="show_passed")

  args = parser.parse_args()

  try:
    with open(args.pfile, 'r') as fh1:
      readpfile = fh1.read()
      try:
        playbook = yaml.load(readpfile)
      except Exception as err:
        print err
    fh1.close()
  except Exception as err:
    print err
    sys.exit(1)
 
    
  if args.snap:
    snap(args.device_name, args.snap[0], playbook)
  elif args.check:
    check(args.device_name, args.check, args.show_passed, playbook)
  else:
    print "Placeholder for --snapcheck feature"
    pass

if __name__ == '__main__':
  main()

