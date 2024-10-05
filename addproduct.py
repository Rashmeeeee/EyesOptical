from flask_wtf import FlaskForm
from wtforms import StringField,SelectField,EmailField,TelField,SubmitField,TextAreaField,BooleanField
from wtforms.validators import Email,DataRequired,Length,Regexp
from flask_wtf.file import FileField,FileAllowed
class AddproductForm(FlaskForm):
     name=StringField('Product Name',validators=[DataRequired()])
     description=TextAreaField('Product Description',validators=[DataRequired()])
     price=StringField('Price',validators=[DataRequired()])
     discountPrice=StringField('Discounted Price')
     checkbox = BooleanField("Has Discount")
     productImage=FileField("Product Image",validators=[FileAllowed(['jpg','png'])])
     submit = SubmitField("Submit")