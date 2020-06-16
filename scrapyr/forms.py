from flask import flash, redirect, url_for
from scrapyr import User
from flask_wtf import FlaskForm
from wtforms import (BooleanField, FileField, PasswordField, StringField, SubmitField)
from wtforms.validators import DataRequired  # , FileRequired, FileAllowed
from . import login_manager

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(user_id)
    except:
        return None

@login_manager.unauthorized_handler
def unauthorized():
    flash('You must be logged in to view that page.', 'warning')
    return redirect(url_for('login'))

class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()] )
    password = PasswordField('password', validators=[DataRequired()] )
    submit = SubmitField('Login')

class UploadForm(FlaskForm):
    excel_file = FileField('Upload File') #, validators = [FileRequired(), FileAllowed(['xlsx'], 'Please uplaoad a valid Excel file.')])
    bool_commit = BooleanField('Run as admin?')
    submit = SubmitField('Submit')
