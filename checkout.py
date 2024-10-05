from flask_wtf import FlaskForm
from wtforms import StringField,SelectField,EmailField,TelField,SubmitField
from wtforms.validators import Email,DataRequired,Length,Regexp

class CheckoutForm(FlaskForm):
     email=EmailField('Email',validators=[DataRequired(),Email()])
     firstname=StringField('First Name',validators=[DataRequired()])
     lastname=StringField('Last Name',validators=[DataRequired()])
     streetaddress =StringField('Street Address',validators=[DataRequired()])
     city=StringField('City',validators=[DataRequired()])
     country=SelectField('Country',choices=["Nepal","India"],validators=[DataRequired()])
     phone=TelField('Phone',validators=[DataRequired(),Regexp(r'^\d{10}$',message="Please enter number"),Length(min=10,max=10)])
     submit = SubmitField("Submit")