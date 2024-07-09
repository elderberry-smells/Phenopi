import os
import subprocess
from datetime import datetime
import paramiko

port = 22
ip_addresses = ['192.168.1.01', ... ]

for ip_add in ip_addresses:

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)

        client.connect(hostname=ip_add, port=port, username="pi")
        
        # make sure the date-time on the pi is set to proper time since it can't update time without internet
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stdin, stdout, stderr = client.exec_command(f"sudo date -s '{time_now} CST'")

    finally:
        client.close()