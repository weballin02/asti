# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FileField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, NumberRange
from flask_wtf.file import FileAllowed
from models import User
from flask_login import current_user

class RegistrationForm(FlaskForm):
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    # Custom validators to check for existing users
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered.')

class LoginForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password',
                             validators=[DataRequired()])
    submit = SubmitField('Login')

class UpdateAccountForm(FlaskForm):
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    submit = SubmitField('Update')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is already registered.')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Post Comment')

class RatingForm(FlaskForm):
    score = IntegerField('Rate (1-5)', validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField('Submit Rating')

class UploadForm(FlaskForm):
    title = StringField('Video Title', validators=[DataRequired(), Length(max=100)])
    video = FileField('Video File', validators=[FileAllowed(['mp4', 'mov', 'avi', 'mkv']), DataRequired()])
    price = IntegerField('Price in USD (e.g., 50 for $50)', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Upload')

class UpdateVideoForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    video = FileField('Update Video File', 
                     validators=[FileAllowed(['mp4', 'mov', 'avi', 'mkv'])])
    price = IntegerField('Price in USD', 
                        validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Update')