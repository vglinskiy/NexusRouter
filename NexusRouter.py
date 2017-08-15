import json
import re
import sys
import getpass
import requests

class NexusRouter(object):
  def __init__(self, device_name):
    """NexusSwitch(device_name, userid, upasswd)
    """
    self.rname  =  device_name
    self.apiurl = "http://"+self.rname+"/ins"
    self.payload =  { "jsonrpc":"2.0", "method":"cli", "params":{ "cmd": "", "version":1.2}, "id":1}
    self.header = {'content-type':'application/json-rpc'}
    self.connected = 0

  def connect(self):
    """ Creates connection to the device to get nxapi_auth cookie  
        to avoid sending username/password for every command
        Must be first method to be called
        From  http://bburl/Fj58C
        A nxapi_auth cookie expires in 600 seconds (10 minutes). 
        This value is a fixed and cannot be adjusted.
    """
    self.username = getpass.getuser()
    self.userpasswd = getpass.getpass("Enter your RADIUS password: ")
    self.payload["params"]["cmd"] = "terminal dont-ask"
    self.session=requests.session()
    self.response = self.session.post(self.apiurl, data=json.dumps(self.payload),\
                     headers=self.header, auth=(self.username, self.userpasswd))
    if self.response.status_code == 401:
      raise ValueError('Wrong username/password')
    elif self.response.status_code != 200: 
      raise ValueError('HTTP Error: ' + str(self.response.status_code) )
    else:
      self.connected = 1

  def conf_command(self, command_list):
    """ Takes ordered list of valid NXOS configuration commands
        and sends them to the router
    """
    if not self.connected:
      raise ValueError("Not connected to the device. Use connect method first to connect to the router")

    self.payload["params"]["cmd"] = "configure terminal"
    _command=[self.payload]
    if type(command_list) is not list:
      raise ValueError("Expecting ordered list of commands, but got "+type(command_list))
    _new_id=2
    for _my_command in command_list:
     _command.append({ "jsonrpc":"2.0", "method":"cli", "params":{ "cmd": _my_command, "version":1.2}, "id":_new_id})
     _new_id += 1
    self.response = self.session.post(self.apiurl, data=json.dumps(_command), headers=self.header)
    if self.response.status_code == 401: 
      raise ValueError('Not authorized, did you use connect method first?')
    elif self.response.status_code == 500:
      for my_error in self.response.json():
        if "error" in my_error.keys() and my_error["error"]["code"] == - 32602:
           error_message = my_error["error"]["data"]["msg"] + " " + _command[my_error["id"]-1]["params"]["cmd"] 
           raise ValueError(error_message)
           break
    elif self.response.status_code != 200:
      raise ValueError('HTTP Error: ' + str(self.response.status_code) )
    else:
      #return self.response.json()
      return "Commands are applied"

  def show_command(self, show_command):
    """ Runs show command on nexus switch and returns json-formatted 
        output, same as when you run "<show command> | json " on cli.
        I.e. "show version | json".   Pipe sign "|" is not allowed.
    """
    if not self.connected:
      raise ValueError("Not connected to the device. Use connect method first to connect to the router")
      sys.exit(1)

    if re.match("\|", show_command):
      raise ValueError('Error: Using pipe sign "|" is not allowed')
    if re.match("[^show ]", show_command):
      raise ValueError('Error: only show commands are supported')
    self.payload["params"]["cmd"] = show_command
    _command=[self.payload]
    self.response = self.session.post(self.apiurl, data=json.dumps(_command), headers=self.header)
    if self.response.status_code == 401: 
      raise ValueError('Not authorized, did you use connect methodo first?')
    elif self.response.status_code == 500:
      raise ValueError(str(self.response.status_code) +" "+self.response.json()["error"]["message"])
    elif self.response.status_code == 200 and self.response.json()["result"] == None: 
      raise ValueError('There is no JSON output for command \"{0}\" or feature not configured'.format(show_command)) 
    elif self.response.status_code != 200:
      raise ValueError('HTTP Error: ' + str(self.response.status_code) )
    else:
      return self.response.json()["result"]["body"]

  def save_config(self):
    """ save configuration to NVRAM
    """
    if not self.connected:
      raise ValueError("Not connected to the device. Use connect method first to connect to the router")

    self.payload["params"]["cmd"] = "copy running-config startup-config"
    print "Saving configuration. Please wait\n"
    response = self.session.post(self.apiurl, data=json.dumps(self.payload), headers=self.header)
    if response.status_code == 200:
      print "Configuration saved. Please proceed.\n"
    else:
      print "Could not save configuration. Please login and run \"copy ru st\" command\n"
      print response.status_code
      sys.exit(1)

