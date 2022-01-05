from datetime import datetime
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, IntegerField, DateField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, IPAddress, NumberRange
from phenopi.models import User, Picam, Experiments
from phenopi import db


class RegistrationForm(FlaskForm):
    username= StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email= StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken, please try another one')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken, please try another one')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('There is no account with that email.  You must register first.')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


class ContactForm(FlaskForm):
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    email= StringField('Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired()])
    submit = SubmitField('Submit')


class AddPiForm(FlaskForm):
    pi_name = StringField('Name of the Pi Camera', validators=[DataRequired()])
    pi_user = StringField('username of the Pi camera', validators=[DataRequired()])
    hostname = StringField('IP address of the Pi camera', validators=[IPAddress()])
    submit = SubmitField('Add Pi')


class PiScheduleForm(FlaskForm):
    # ┌───────────── minute (0 - 59)
    # │ ┌───────────── hour (0 - 23)
    # │ │ ┌───────────── day of the month (1 - 31)
    # │ │ │ ┌───────────── month (1 - 12)
    # │ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday;
    # │ │ │ │ │                                   7 is also Sunday on some systems)
    # │ │ │ │ │
    # │ │ │ │ │
    # * * * * * command to execute
    experiment = StringField('Experiment Name', validators=[DataRequired()])
    # start_date = DateField('DatePicker', format='%Y-%M-%d', validators=[DataRequired()])
    start_date = StringField('Start Date', validators=[DataRequired('Please select start date')])
    end_date = StringField('End Date', validators=[DataRequired('Please select end date')])
    start_images = SelectField('Start Time am (each day)', choices=[
        ('8:00', '8:00'), ('8:30', '8:30'), ('9:00', '9:00'), ('9:30', '9:30'), ('10:00', '10:00'), ('10:30', '10:30'),
        ('11:00', '11:00'), ('11:30', '11:30'), ('12:00', '12:00')], validators=[DataRequired()])
    end_images = SelectField('End Time pm (each day)', choices=[
        ('17:00', '5:00'), ('17:30', '5:30'), ('18:00', '6:00'), ('18:30', '6:30'), ('19:00', '7:00'), ('19:30', '7:30'),
        ('20:00', '8:00'), ('20:30', '8:30'), ('21:00', '9:00'), ('21:30', '9:30')], validators=[DataRequired()])
    interval = SelectField('Interval (minutes between images)', choices=[
        ('5', '5'), ('10', '10'), ('30', '30'), ('60', '60')], validators=[DataRequired()])
    submit = SubmitField('Schedule the Pi Timelapse')


###  setting up the checkbox and multi pi schedule forms ###

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ExpScheduleForm(FlaskForm):
    # ┌───────────── minute (0 - 59)
    # │ ┌───────────── hour (0 - 23)
    # │ │ ┌───────────── day of the month (1 - 31)
    # │ │ │ ┌───────────── month (1 - 12)
    # │ │ │ │ ┌───────────── day of the week (0 - 6) (Sunday to Saturday;
    # │ │ │ │ │                                   7 is also Sunday on some systems)
    # │ │ │ │ │
    # │ │ │ │ │
    # * * * * * command to execute
    
    
    # checkboxes for the selection of pis.  If DB doesm't exist yet, this part causes error becaue no tables exist as of yet!
    pis = Picam.query.filter(Picam.status.contains('idle'))
    choices = [(pi.id, pi.piname) for pi in pis] # just the pi names and pi ids in a tuple for the selections
    avail_pis = MultiCheckboxField('Available Pis', choices=choices, coerce=int)
    
    
    # remainder of the experiment
    experiment = StringField('Experiment Name', validators=[DataRequired()])
    start_date = StringField('Start Date', validators=[DataRequired('Please select start date')])
    end_date = StringField('End Date', validators=[DataRequired('Please select end date')])
    start_images = SelectField('Start Time am (each day)', choices=[
        ('8:00', '8:00'), ('8:30', '8:30'), ('9:00', '9:00'), ('9:30', '9:30'), ('10:00', '10:00'), ('10:30', '10:30'),
        ('11:00', '11:00'), ('11:30', '11:30'), ('12:00', '12:00')], validators=[DataRequired()])
    end_images = SelectField('End Time pm (each day)', choices=[
        ('17:00', '5:00'), ('17:30', '5:30'), ('18:00', '6:00'), ('18:30', '6:30'), ('19:00', '7:00'), ('19:30', '7:30'),
        ('20:00', '8:00'), ('20:30', '8:30'), ('21:00', '9:00'), ('21:30', '9:30')], validators=[DataRequired()])
    interval = SelectField('Interval (minutes between images)', choices=[
        ('5', '5'), ('10', '10'), ('30', '30'), ('60', '60')], validators=[DataRequired()])
    submit = SubmitField('Schedule the Pi Timelapse')


# use to set up form to reset password, not required just yet
# class UpdateAccountForm(FlaskForm):
#     username= StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
#     email= StringField('Email', validators=[DataRequired(), Email()])
#     picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
#     submit = SubmitField('Update')
#
#     def validate_username(self, username):
#         if username.data != current_user.username:
#             user = User.query.filter_by(username=username.data).first()
#             if user:
#                 raise ValidationError('That username is taken, please try another one')
#
#     def validate_email(self, email):
#         if email.data != current_user.email:
#             user = User.query.filter_by(email=email.data).first()
#             if user:
#                 raise ValidationError('That email is taken, please try another one')