from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, BooleanField, URLField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, URL, Optional

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class PasswordEntryForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    username = StringField('Username/Email', validators=[DataRequired(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired()])
    url = URLField('Website URL', validators=[Optional(), URL(), Length(max=255)])
    category = SelectField('Category', choices=[
        ('', 'Select Category'),
        ('social', 'Social Media'),
        ('shopping', 'Shopping'),
        ('banking', 'Banking'),
        ('work', 'Work'),
        ('email', 'Email'),
        ('entertainment', 'Entertainment'),
        ('other', 'Other')
    ])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save Password')

class SearchForm(FlaskForm):
    query = StringField('Search', validators=[Optional()])
    submit = SubmitField('Search')
    
class SubscriptionForm(FlaskForm):
    """Form for subscription checkout"""
    plan_id = HiddenField('Plan ID', validators=[DataRequired()])
    submit = SubmitField('Subscribe')
