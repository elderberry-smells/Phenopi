import os
import secrets
import subprocess
from datetime import datetime
import paramiko
from PIL import Image
from flask import url_for, current_app
from phenopi import mail
from flask_mail import Message
import imageio
from pathlib import Path
import glob
from phenopi.models import User, Picam, Experiments
from phenopi import db
from crontab import CronTab


def save_picture(pic, piname):
    """ Save user image to file system"""
    pic_path = Path.cwd() / 'phenopi'/ 'static' / pic
    # random_hex = secrets.token_hex(8)
    f_ext = Path(pic_path).suffix
    picture_fn = f'{piname}_profile{f_ext}'
    save_path = Path.cwd() / 'phenopi' / 'static'/ piname / 'profile_pics' / picture_fn
    pic_db = f'{piname}/profile_pics/{picture_fn}'

    # resize the image, save the thumbnail
    output_size = (350, 250)
    i = Image.open(pic_path)
    i.thumbnail(output_size)
    i.save(save_path)

    return pic_db


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender='thisis100percentnotfake@gmail.com', recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link: 
{url_for('users.reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made
'''
    mail.send(msg)


def contact_request(f_name, l_name, email, subject):
    msg = Message('Contact Request', sender='thisis100percentnotfake@gmail.com', recipients=['brianjames567@gmail.com'])
    msg.body = f'''Sender:  {f_name} {l_name}
email: {email}

Subject Body:
{subject}

This was an automated email generated at www.briancjames.ca
'''
    mail.send(msg)


def create_cron_job(command, start_minute, start_hour, end_hour, start_day, end_day, start_month, end_month, interval, user=None):
    # generate the necessary cron job commands with the schedule inputs
    cron = CronTab()
    
    # make the bayer image the first image of the day
    bayer = cron.new(command=command.replace("False", "True"))
    bayer.minute.on(start_minute)
    bayer.hour.on(start_hour)
    bayer.day.during(start_day, end_day)
    bayer.month.during(start_month, end_month)
    
    # make the remainder of the cron jobs
    job = cron.new(command=command)
    job.minute.on(start_minute)
    
    if interval >= 60:
        interval = interval // 60
        job.hour.during(start_hour, end_hour).every(interval)
    else:
        job.minute.every(interval)
        job.hour.during(start_hour, end_hour)

    job.day.during(start_day, end_day)
    job.month.during(start_month, end_month)
    
    return bayer, job


def generate_schedule(schedule, pi, userid):

    # create a directory for the experiment from that pi to be saved on the server
    pi_folder = Path(f'phenopi/static/{pi.piname}')
    pi_folder.mkdir(parents=True, exist_ok=True)
    exp_folder = Path(f'phenopi/static/{pi.piname}/experiments/{schedule["experiment"]}')
    exp_folder.mkdir(parents=True, exist_ok=True)
    fname = f'{pi_folder}/cronjobs/{schedule["experiment"]}_cronjob.txt'

    month_days = {'1': '31', '2': '28', '3': '31', '4': '30', '5': '31', '6': '30',
                  '7': '31', '8':'31', '9': '30', '10': '31', '11': '30', '12': '31'}

   # Extract schedule details
    start_hour, start_minute = map(int, schedule['start'].split(':'))
    end_hour, end_minute = map(int, schedule['end'].split(':'))
    interval = int(schedule['interval'])

    start_date = datetime.strptime(schedule['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(schedule['end_date'], '%Y-%m-%d')

    start_day = start_date.day
    start_month = start_date.month
    end_day = end_date.day
    end_month = end_date.month

    command = f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} -p {pi.id} -u {userid} -b False'

    cron_list = [] # make a list of the cron outputs to write to a txt file
    if start_date.year != end_date.year or start_month > end_month:
        # Create job for the remainder of the first year
        bayer1, job1 = create_cron_job(command, start_minute, start_hour, end_hour, start_day, 31, start_month, 12, interval, user=userid)
        cron_list.append(str(bayer1)+'\n') # add the newline to end of each cron job
        cron_list.append(str(job1)+'\n')

        # Create job for the next year
        bayer2, job2 = create_cron_job(command, start_minute, start_hour, end_hour, 1, end_day, 1, end_month, interval, user=userid)
        cron_list.append(str(bayer2)+'\n') # add the newline to end of each cron job
        cron_list.append(str(job2))

    else:
        # Single job for the same year
        bayer1, job1 = create_cron_job(command, start_minute, start_hour, end_hour, start_day, end_day, start_month, end_month, interval, user=userid)
        cron_list.append(str(bayer1)+'\n') # add the newline to end of each cron job
        cron_list.append(str(job1))

    # write out the cron job
    with open(fname, 'w', encoding='utf-8') as outcron:
        outcron.write(f'#  Setting up schedule for experiment: {schedule["experiment"]}\n')
        outcron.write(f'#  Running from {schedule["start_date"]} - {schedule["end_date"]}\n')
        outcron.write(f'#  Images between {schedule["start"]} and {schedule["end"]} with images every {interval} minutes\n\n')

        outcron.write("""
            # ┌───────────── minute (0 - 59)
            # │ ┌───────────── hour (0 - 23)
            # │ │ ┌───────────── day of the month (1 - 31)
            # │ │ │ ┌───────────── month (1 - 12)
            # │ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday;
            # │ │ │ │ │                                   7 is also Sunday on some systems)
            # │ │ │ │ │
            # │ │ │ │ │
            # * * * * * command to execute')\n\n""")

        outcron.writelines(cron_list)
        
    # transfer that cron file to the pi
    subprocess.run(["scp", fname, f"{pi.username}@{pi.hostname}:/home/pi/Desktop/phenopi_cron"])
    pi_cronfile = f'/home/pi/Desktop/phenopi_cron/{schedule["experiment"]}_cronjob.txt'

    port = 22
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)

        client.connect(hostname=pi.hostname, port=port, username=pi.username)

        # make sure the date-time on the pi is set to proper time since it can't update time without internet
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stdin, stdout, stderr = client.exec_command(f"sudo date -s '{time_now} CST'")

        # remove any cron jobs currently running
        remove_command = f'crontab -r'
        stdin, stdout, stderr = client.exec_command(remove_command)

        # make the newly transferred cronfile as the the crontab    
        cron_command = f'crontab {pi_cronfile}'
        stdin, stdout, stderr = client.exec_command(cron_command)


    finally:
        client.close()

    return fname
    '''
    # get the minutes and hours from the schedule
    start_hour, start_minute = schedule['start'].split(':')
    end_hour, end_minute = schedule['end'].split(':')
    middle_hours = [i for i in range(int(start_hour) + 1, int(end_hour))]
    interval = int(schedule['interval'])

    #  get the days and months from the schedule
    start_day = datetime.strptime(schedule['start_date'], '%Y-%M-%d').strftime('%d')
    start_month = int(datetime.strptime(schedule['start_date'], '%Y-%M-%d').strftime('%M'))
    end_day = datetime.strptime(schedule['end_date'], '%Y-%M-%d').strftime('%d')
    end_month = int(datetime.strptime(schedule['end_date'], '%Y-%M-%d').strftime('%M'))

    # get a list of the months to capture in order of occurance:
    if start_month > end_month:  # it spans over to the following year
        month_list = [i for i in range(start_month, 13, 1)]  # get to the remainder of the year
        for rest in range(1, end_month + 1, 1):
            month_list.append(rest)
    else:
        month_list = [i for i in range(start_month, end_month + 1, 1)]

    # if only running for specific days in 1 month
    if len(month_list) == 1:
        days = f'{int(start_day)}-{int(end_day)}' if start_day != end_day else f'{int(start_day)}'
    else:
        days = f'{int(start_day)}-{month_days[str(start_month)]}'

    if len(month_list) >= 3:
        middle_months = month_list[1:-1]  # grab the middle months
    else:
        middle_months = False

    # get the interval times the remainder of the first hour (start intervals after bayer image)
    if int(interval) == 30:  # we would only need 0 and 30 for every hour
        firsth_intervals = '30' if start_minute == '00' else False

    elif int(interval) != 60:
        firsth_intervals = ','.join(str(x) for x in range(int(start_minute) + interval, 56, interval))

    else:  # each image is an hour in between so no firsth_interval
        firsth_intervals = False

    # get the interval times for the last hour of the day (if end time falls on a 30)
    if end_minute == '30':
        lasth_intervals = ','.join(str(x) for x in range(0, 30, interval))

    else:
        lasth_intervals = False

    # if the interval is 60 minutes, change how the images are captured for the rest_day variables
    if str(interval) == '60':
        restday_mins = '30' if start_minute == '30' else '0'
    else:
        restday_mins = f'*/{str(interval)}'

    # get the last picture of every day (minute and hour)
    bayer_end = f'{int(end_minute)} {int(end_hour)}'

    with open(fname, 'w') as outcron:
        outcron.write(f'#  Setting up schedule for experiment: {schedule["experiment"]}\n')
        outcron.write(f'#  Running from {schedule["start_date"]} - {schedule["end_date"]}\n')
        outcron.write(
            f'#  Images between {schedule["start"]} and {schedule["end"]} with images every {interval} minutes\n\n')

        outcron.writelines("""
        # ┌───────────── minute (0 - 59)
        # │ ┌───────────── hour (0 - 23)
        # │ │ ┌───────────── day of the month (1 - 31)
        # │ │ │ ┌───────────── month (1 - 12)
        # │ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday;
        # │ │ │ │ │                                   7 is also Sunday on some systems)
        # │ │ │ │ │
        # │ │ │ │ │
        # * * * * * command to execute')\n\n""")

        ################################ first month schedule values ###################################################
        bayer_start_month = f'{int(start_minute)} {int(start_hour)} {days} ' \
                            f'{int(start_month)} *'

        restday_start_month = f'{restday_mins} {int(middle_hours[0])}-{int(middle_hours[-1])} ' \
                              f'{days} {int(start_month)} *'

        ################################## write out the first months images  ##########################################
        outcron.write(f'# first image of the day at {schedule["start"]} with Bayer data -- first month\n')
        outcron.write(f'{bayer_start_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                      f'-p {pi.id} -u {userid} -b True\n\n')
        if firsth_intervals:
            first_hour_start_month = f'{firsth_intervals} {int(start_hour)} {int(start_day)}-{month_days[str(start_month)]} ' \
                                     f'{int(start_month)} *'
            outcron.write(f'# images being taken between {int(start_hour)}:{int(start_minute)+interval:02d}am '
                          f'and {int(start_hour)}:55am -- first month\n')
            outcron.write(f'{first_hour_start_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                          f'-p {pi.id} -u {userid} -b False\n\n')
        outcron.write(f'# images being taken between {int(start_hour)+1}:00am and {int(end_hour)}pm -- first month\n')
        outcron.write(f'{restday_start_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                      f'-p {pi.id} -u {userid} -b False\n\n')
        if lasth_intervals:
            last_hour_start_month = f'{lasth_intervals} {int(end_hour)} {int(start_day)}-{month_days[str(start_month)]}' \
                                    f' {int(start_month)} *'
            outcron.write(f'# images being taken in last hour, between {end_hour}:00pm '
                          f'and {schedule["end"]}pm - first month\n')
            outcron.write(f'{last_hour_start_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                          f'-p {pi.id} -u {userid} -b False\n\n')
        outcron.write(f'# last image of the day at {schedule["end"]} with Bayer data being captured - first month\n')
        outcron.write(f'{bayer_end} {int(start_day)}-{month_days[str(start_month)]} {int(start_month)} * '
                      f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                      f'-p {pi.id} -u {userid} -b True\n\n')

        ################################    middle months schedule    #################################################
        if middle_months:  # a middle month exists (not just start and end month)
            if len(middle_months) == 1:
                middle_span = middle_months[0]  # don't need multiples in months (ie 2-4) in cron scheduler
            else:
                middle_span = f'{middle_months[0]}-{middle_months[-1]}'

            if middle_months[0] < month_list[-1]:  # doesn't spill over to next year
                bayer_mid_months = f'{int(start_minute)} {int(start_hour)} * {middle_span} *'
                restday_mid_months = f'{restday_mins} {middle_hours[0]}-{middle_hours[-1]} * {middle_span} *'

                # write out the middle months if span over 3+ months
                outcron.write(f'# first image of the day at {schedule["start"]} with Bayer data -- middle months\n')
                outcron.write(f'{bayer_mid_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')
                if firsth_intervals:
                    first_hour_mid_months = f'{firsth_intervals} {int(start_hour)} * {middle_span} *'
                    outcron.write(
                        f'# images being taken between {schedule["start"]}am and {int(start_hour)}:55am -- middle months\n')
                    outcron.write(f'{first_hour_mid_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]}'
                                  f' -p {pi.id} -u {userid} -b False\n\n')
                outcron.write(f'# images being taken between {int(start_hour) + 1}:00am '
                              f'and {int(end_hour)}:00pm -- middle months\n')
                outcron.write(f'{restday_mid_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b False\n\n')

                if lasth_intervals:
                    lasth_mid_months = f'{lasth_intervals} {int(end_hour)} * {middle_months[0]}-{middle_months[-1]} *'
                    outcron.write(f'# images being taken in last hour, between {end_hour}:00 '
                                  f'and {schedule["end"]} -- middle months\n')
                    outcron.write(f'{lasth_mid_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                                  f'-p {pi.id} -u {userid} -b False\n\n')
                outcron.write(
                    f'# last image of the day at {schedule["end"]} with Bayer data being captured -- middle months\n')
                outcron.write(f'{bayer_end} * {middle_months[0]}-{middle_months[-1]} * '
                              f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')

            else:  # schedule spills into following year
                # fill out remaining months of year
                if str(middle_months[0]) == '12':
                    end_year = middle_months[0]
                else:
                    end_year = f'{middle_months[0]}-12'

                bayer_end_months = f'{int(start_minute)} {int(start_hour)} * {end_year} *'
                restday_end_months = f'{restday_mins} {middle_hours[0]}-{middle_hours[-1]} * {end_year} *'

                # write out the remainder of the year
                outcron.write(
                    '# first image of the day with Bayer data being captured -- up to years end\n')
                outcron.write(f'{bayer_end_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')
                if firsth_intervals:
                    first_hour_end_months = f'{firsth_intervals} {int(start_hour)} * {end_year} *'
                    outcron.write(
                        f'# images being taken between {schedule["start"]}am and {int(start_hour)}:55am - up to years end\n')
                    outcron.write(
                        f'{first_hour_end_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]}'
                        f' -p {pi.id} -u {userid} -b False\n\n')
                outcron.write(f'# images being taken between {int(start_hour) + 1}:00am '
                              f'and {int(end_hour)}pm - up to years end\n')
                outcron.write(
                    f'{restday_end_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                    f'-p {pi.id} -u {userid} -b False\n\n')

                if lasth_intervals:
                    lasth_end_months = f'{lasth_intervals} {int(end_hour)} * {end_year} *'
                    outcron.write(f'# images being taken in last hour, between {end_hour}:00 '
                                  f'and {schedule["end"]} - up to years end\n')
                    outcron.write(
                        f'{lasth_end_months} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                        f'-p {pi.id} -u {userid} -b False\n\n')

                outcron.write(
                    f'# last image of the day at {schedule["end"]} with Bayer data being captured - up to years end\n')
                outcron.write(f'{bayer_end} * {end_year} * '
                              f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')

                # complete the remainder of the middle months schedule (start of the new year until end month)
                if str(middle_months[-1]) == '1':  # the last middle month is january so no need to make a series
                    begin_year = middle_months[-1]
                else:
                    begin_year = f'1-{middle_months[-1]}'

                bayer_start_year = f'{int(start_minute)} {int(start_hour)} * {begin_year} *'
                restday_begin_year = f'{restday_mins} {middle_hours[0]}-{middle_hours[-1]} * {begin_year} *'

                outcron.write(
                    '# first image of the day at 8:35am with Bayer data being captured -- start year to end month\n')
                outcron.write(f'{bayer_start_year} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')
                if firsth_intervals:
                    first_hour_begin_year = f'{firsth_intervals} {int(start_hour)} * {begin_year} *'
                    outcron.write(
                        f'# images being taken between {schedule["start"]}am and {int(start_hour)}:55am - start year to end month\n')
                    outcron.write(
                        f'{first_hour_begin_year} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]}'
                        f' -p {pi.id} -u {userid} -b False\n\n')
                outcron.write(f'# images being taken between {int(start_hour) + 1}:00am '
                              f'and {int(end_hour)}pm - start year to end month\n')
                outcron.write(
                    f'{restday_begin_year} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                    f'-p {pi.id} -u {userid} -b False\n\n')

                if lasth_intervals:
                    lasth_begin_year = f'{lasth_intervals} {int(end_hour)} * {begin_year} *'
                    outcron.write(f'# images being taken in last hour, between {end_hour}:00 '
                                  f'and {schedule["end"]} - start year to end month\n')
                    outcron.write(
                        f'{lasth_begin_year} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                        f'-p {pi.id} -u {userid} -b False\n\n')
                outcron.write(
                    f'# last image of the day at {schedule["end"]} with Bayer data being captured -- start year to end month\n')
                outcron.write(f'{bayer_end} * {begin_year} * '
                              f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b True\n\n')

        ############################# last month schedule (if last month different from start month  ###################
        if start_month != end_month:
            bayer_last_month = f'{int(start_minute)} {int(start_hour)} 1-{int(end_day)} {int(end_month)} *'
            restday_last_month = f'{restday_mins} {middle_hours[0]}-{middle_hours[-1]} ' \
                                 f'1-{int(end_day)} {int(end_month)} *'

            # write out last month captures if span over multiple months
            outcron.write('# first image of the day at 8:35am with Bayer data being captured - end month\n')
            outcron.write(f'{bayer_last_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                          f'-p {pi.id} -u {userid} -b True\n\n')
            if firsth_intervals:
                first_hour_last_month = f'{firsth_intervals} {int(start_hour)} 1-{int(end_day)} {int(end_month)} *'
                outcron.write(f'# images being taken between {schedule["start"]}am '
                              f'and {int(start_hour)}:55am - end month\n')
                outcron.write(f'{first_hour_last_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b False\n\n')
            outcron.write(f'# images being taken between {int(start_hour) + 1}:00am '
                          f'and {int(end_hour)}pm -- end month\n')
            outcron.write(f'{restday_last_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                          f'-p {pi.id} -u {userid} -b False\n\n')
            if lasth_intervals:
                lasth_last_month = f'{lasth_intervals} {int(end_hour)} 1-{int(end_day)} {int(end_month)} *'
                outcron.write(f'\n# images being taken between {end_hour}:00pm '
                              f'and {schedule["end"]}pm - end month\n')
                outcron.write(f'{lasth_last_month} /usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                              f'-p {pi.id} -u {userid} -b False\n\n')
            outcron.write(
                f'# last image of the day at {schedule["end"]} with Bayer data being captured -- end month\n')
            outcron.write(f'{bayer_end} 1-{int(end_day)} {int(end_month)} * '
                          f'/usr/local/bin/python3.8 /home/pi/phenopi/capture.py -e {schedule["experiment"]} '
                          f'-p {pi.id} -u {userid} -b True\n\n')
        outcron.write('# Cancel the crontab once the schedule ends\n')
        outcron.write(f'{int(end_minute) + 1} {end_hour} {end_day} {end_month} * crontab -r\n')

    # transfer that cron file to the pi
    subprocess.run(["scp", fname, f"{pi.username}@{pi.hostname}:/home/pi/Desktop/phenopi_cron"])
    pi_cronfile = f'/home/pi/Desktop/phenopi_cron/{schedule["experiment"]}_cronjob.txt'

    port = 22
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)

        client.connect(hostname=pi.hostname, port=port, username=pi.username)
        
        # make sure the date-time on the pi is set to proper time since it can't update time without internet
        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stdin, stdout, stderr = client.exec_command(f"sudo date -s '{time_now} CST'")
        
        # remove any cron jobs currently running
        remove_command = f'crontab -r'
        stdin, stdout, stderr = client.exec_command(remove_command)

        # make the newly transferred cronfile as the the crontab    
        cron_command = f'crontab {pi_cronfile}'
        stdin, stdout, stderr = client.exec_command(cron_command)


    finally:
        client.close()

    return fname
'''

def pi_picture(uname, pi_ip, command):
    port = 22

    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)

        client.connect(pi_ip, port=port, username=uname)

        stdin, stdout, stderr = client.exec_command(command)
        print(stdout.read().decode('utf-8'))
        return stdout.read().decode('utf-8')
        # take_pic = 'python3 /home/pi/Desktop/pi_scripts/single_capture/capture.py -d /home/pi/Desktop/pi_pictures -e linux_capture -b False'
        # stdin, stdout, stderr = client.exec_command(take_pic)

    finally:
        client.close()


def cancel_imaging(pi):
    port = 22
    try:
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.WarningPolicy)

        client.connect(pi.hostname, port=port, username=pi.username)

        stdin, stdout, stderr = client.exec_command("crontab -r")

    finally:
        client.close()


def pi_gif(piname):
    # grab all the images used for the profile pictures (smaller resolution images from Pi) and make a gif
    path_images = Path.cwd() / 'phenopi'/ 'static' / f'{piname}' / 'profile_pics'
    filenames = glob.glob(f'{path_images}/*.jpg')

    if len(filenames) != 0:
        images = []
        for filename in filenames:
            images.append(imageio.imread(filename))
        gif_name =  Path.cwd() / 'phenopi'/ 'static' / f'{piname}' / f'{piname}.gif'
        gif_db = f'{piname}/{piname}.gif'
        kargs = {'duration': 1}

        imageio.mimsave(gif_name, images, **kargs)
    else:
        return None

    return gif_db
