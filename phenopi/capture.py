#!/usr/bin/python
import os
import subprocess
from pathlib import Path
from datetime import datetime, date, time
from time import sleep
import socket
from picamera import PiCamera
import os.path
import argparse
import paramiko
from paramiko import SSHClient
from scp import SCPClient


def options():
    parser = argparse.ArgumentParser(description="taking scheduled single images of flats with raspberry pi camera.")
    parser.add_argument('-e', '--exp',
                        help='Name of experiment being captured by images, for example "canola_phenotyping"',
                        required=True)
    parser.add_argument('-b', '--bayer', default='False', help='<True|False> Add Bayer data to the image capture',
                        required=True)
    parser.add_argument('-p', '--piid', required=True, help='the raspberry pi id (integer) from database')
    parser.add_argument('-u', '--userid', required=True, help='the user id (integer) from database')
    args = parser.parse_args()

    return args


def update_img_db(ssh_client, img_name, userid, piid, exp, pi):
    
    try:
        ssh_client.set_missing_host_key_policy(paramiko.WarningPolicy)

        # set these values into ENV VARIABLE so the IP isn't visible in this script?
        pi_cmd = "python3 /home/bioinf/pi/phenopi/update_img_db.py -i {0} -e {1} -u {2} -p {3} -c {4}".format(img_name, exp, userid, piid, pi)
        stdin, stdout, stderr = ssh_client.exec_command(pi_cmd)
        # command will run the python script on the server and add the information of the image to the database

        return stdin, stdout, stderr

    finally:
        ssh_client.close()


def capture():
    # get the options into the function
    args = options()
    exp = args.exp
    piid = args.piid
    uid = args.userid
    bayer_data = args.bayer.lower()

    date_now = datetime.now().strftime('%Y-%m-%d_%H:%M')  # current date/time
    file_path = '/home/pi/phenopi/{0}'.format(exp)
    Path(file_path).mkdir(parents=True, exist_ok=True)  # make the directory for experiment if not exists
    imgnum_path = '{0}/imageNumber.txt'.format(file_path)
    pi = socket.gethostname()

    # determine what the next number in the series of images is from the txt file log
    if Path(imgnum_path).is_file():
        with open(imgnum_path, 'r') as img:
            imgnum = int(img.readline()) + 1
    else:
        os.system('echo "00000" >> {0}'.format(imgnum_path))
        imgnum = 1

    image_num = str(imgnum).zfill(6)  # get the image number to append to the img name


    if bayer_data == 'true':  # add bayer data to the image
        image_fname = '{0}/{1}-{2}_{3}_bayer.jpeg'.format(file_path, pi, image_num, date_now)
        camera.capture(image_fname, quality=100, bayer=True)
    else:
        image_fname = '{0}/{1}-{2}_{3}.jpeg'.format(file_path, pi, image_num, date_now)
        camera.capture(image_fname, quality=100)

    imgnum += 1
    os.system('rm {0}'.format(imgnum_path))  # delete the imagenumber file
    os.system('echo {0} >> {1}'.format(image_num, imgnum_path))  # make a new imagenumber file

    # transfer image using connection via paramiko
    client = SSHClient()
    client.load_system_host_keys()
    client.connect(hostname="192.168.0.101", port=22, username="bioinf")

    with SCPClient(client.get_transport()) as scp:
        scp.put(image_fname, recursive=True, remote_path=f'/home/bioinf/pi/phenopi/static/{pi}/experiments/{exp}')
    
    stdin, stdout, stderr = update_img_db(client, image_fname, uid, piid, exp, pi)
    # print(stdout, stderr)


if __name__ == '__main__':
    #  initialize the camera
    camera = PiCamera()
    sleep(1)  # allow the camera to warm up

    capture()
