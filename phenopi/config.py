import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = '08ce16b3e9f7a1e90861929d6f9d303a'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'thisis100percentnotfake@gmail.com'
    MAIL_PASSWORD = 'etxp afzg fpqf exup'
    #MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    #MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')