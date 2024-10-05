from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField
from wtforms.validators import Email, DataRequired, Length, EqualTo, ValidationError
import re


class SignupForm(FlaskForm):
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[
                                     DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    def validate_password(self, password):
        # Check for password length
        if len(password.data) < 8:
            raise ValidationError(
                'Password must be at least 8 characters long.')

        # Check for uppercase, lowercase, digit, and special character
        if not re.search(r'[A-Z]', password.data):
            raise ValidationError(
                'Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password.data):
            raise ValidationError(
                'Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password.data):
            raise ValidationError('Password must contain at least one number.')
        if not re.search(r'[@$!%*?&]', password.data):
            raise ValidationError(
                'Password must contain at least one special character (@, $, !, %, *, ?, &).')


class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField("Login")
