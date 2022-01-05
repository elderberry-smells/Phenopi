from datetime import datetime
from phenopi import db, login_manager
from flask_login import UserMixin


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    exps = db.relationship('Experiments', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"


class Picam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    piname = db.Column(db.String, unique=True, nullable=False)
    username = db.Column(db.String, unique=False, nullable=False)
    hostname = db.Column(db.String, unique=True, nullable=False)
    status = db.Column(db.String, unique=False, default='idle')
    image_file = db.Column(db.String, nullable=False, default='default.png')
    pics = db.relationship('Experiments', backref='camera', lazy=True)

    def __repr__(self):
        return f"Camera('{self.piname}', '{self.status}')"


class Experiments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date_submitted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exp_name = db.Column(db.String, unique=False, nullable=False)
    status = db.Column(db.String, unique=False, default='Running')
    start_date = db.Column(db.String, unique=False)
    end_date = db.Column(db.String, unique=False)
    start_time = db.Column(db.String, unique=False)
    end_time = db.Column(db.String, unique=False)
    img_interval = db.Column(db.Integer, unique=False)
    pi_id = db.Column(db.Integer, db.ForeignKey('picam.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Exp('{self.exp_name}', '{self.date_submitted}', {self.start_date},'{self.end_date}', '{self.start_time}', '{self.end_time}')"


class PiImages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exp_name = db.Column(db.String, unique=False, nullable=False)
    exp_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    pi_id = db.Column(db.Integer, db.ForeignKey('picam.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date_image = db.Column(db.String, nullable=False)
    image_fname = db.Column(db.String)

    def __repr__(self):
        return f"Img('{self.exp_name}', '{self.date_image}','{self.image_fname}', '{self.user_id}')"