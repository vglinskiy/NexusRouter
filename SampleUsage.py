import json
import requests
import getpass
from NexusRouter import NexusRouter
device_name="n7700"
userid=getpass.getuser()
upasswd=getpass.getpass()
myrouter=NexusRouter(device_name, userid, upasswd)
myrouter=NexusRouter(device_name)
myrouter.connect()
my_commands=["interface Ethernet1/2", "blahblah", "no shutdown"]
show_command="show version"
try:
  output=myrouter.conf_command(my_commands)
except Exception as err:
  print err

