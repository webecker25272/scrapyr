from flask_wtf import FlaskForm
from wtforms import (BooleanField, FileField, PasswordField, StringField, SubmitField)
from wtforms.validators import DataRequired  # , FileRequired, FileAllowed


class LoginForm(FlaskForm):
    username = StringField('username', validators=[DataRequired()] )
    password = PasswordField('password', validators=[DataRequired()] )
    submit = SubmitField('Login')

class UploadForm(FlaskForm):
    excel_file = FileField('Upload File') #, validators = [FileRequired(), FileAllowed(['xlsx'], 'Please uplaoad a valid Excel file.')])
    bool_commit = BooleanField('Run as admin?')
    submit = SubmitField('Submit')
