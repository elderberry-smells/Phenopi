import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'seceret_key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'you_admin@email.com'
    MAIL_PASSWORD = 'password for your email'  # probably want to put these into os.envrions so its not hard coded
