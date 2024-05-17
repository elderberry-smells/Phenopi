#!/usr/bin/python
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime


def options():
    parser = argparse.ArgumentParser(description="taking scheduled single images of flats with raspberry pi camera.")
    parser.add_argument('-i', '--image', help='image file name being uploaded', required=True)
    parser.add_argument('-e', '--exp', help='experiment name from the image capture', required=True)
    parser.add_argument('-u', '--userid', required=True, help='the user id (integer) from database')
    parser.add_argument('-p', '--piid', required=True, help='the raspberry pi id (integer) from database')
    parser.add_argument('-c', '--picam', required=True, help='The camera that took the picture')
    args = parser.parse_args()

    return args


def db_connection(exp, pi, user, date_img, img, picam):
    # connect to the database using sqlite3 and insert the image record into pi_images table
    db = '/home/bioinf/piapp/phenopi/app.db'
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    img_name = Path(img).name
    date_now = datetime.utcnow()

    img_path = f'{picam}/experiments/{exp}/{img_name}'
    # determine the experiment id from the database using the expeiriment name
    exp_query = f"SELECT id FROM experiments WHERE exp_name='{exp}' AND pi_id={int(pi)}"
    expid = cur.execute(exp_query).fetchall()
    entry = [(date_now, str(exp), int(expid[0][0]), int(pi), int(user), str(date_img), str(img_path))]
    cur.executemany("INSERT INTO pi_images (upload_date, exp_name, exp_id, pi_id, user_id, date_image, image_fname) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?);", entry)

    conn.commit()
    conn.close()


def main():
    args = options()
    img = args.image  # image name
    experiment = args.exp  # experiment name
    piid = args.piid  # picam id
    uid = args.userid  # user id
    picam = args.picam  # picam name

    # slice the image name to get the the datetime from it
    if 'bayer' in img:
        date_image = img[-27:-11]
        date_image = date_image.replace('_', ' ')

    else:
        date_image = img[-21:-5]
        date_image = date_image.replace('_', ' ')

    db_connection(experiment, piid, uid, date_image, img, picam)


if __name__ == '__main__':
    main()
