import datetime
from flask import Flask, render_template, flash, redirect, url_for, request, Response, send_file, jsonify
from addproduct import AddproductForm
from backend.emotion_detect.emotion_detector import EmotionDetector
from backend.image_object import ImageObject
from backend.landmark_detection import LandmarkDetector
from backend.overlay_accessory import overlay_accessory
from checkout import CheckoutForm
from flask_sqlalchemy import SQLAlchemy
import os
import cv2
from backend.record import Capture, generate_video, save_image, cache
from backend.pre_process import preprocess
import numpy as np
import uuid
from login import LoginForm, SignupForm
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from flask_bcrypt import generate_password_hash, check_password_hash
import torch
from model import NeuralNet
from nltk_utils import bag_of_words, tokenize
import random
import requests
import time
import json
from flask import session

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Install with: pip install python-dotenv")

from camera import Camera
app = Flask(__name__)
# Load chatbot model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

with open('intents.json', 'r', encoding='utf-8') as json_data:
    intents = json.load(json_data)

FILE = "data.pth"
data = torch.load(FILE)

input_size = data["input_size"]
hidden_size = data["hidden_size"]
output_size = data["output_size"]
all_words = data['all_words']
tags = data['tags']
model_state = data["model_state"]

model = NeuralNet(input_size, hidden_size, output_size).to(device)
model.load_state_dict(model_state)
model.eval()

bot_name = "Sam"

app.config['SECRET_KEY'] = "de9e5b220476ba0aba47040eb9b2fea9"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chasmaghar.db'
bcrypt = Bcrypt(app)
login_mananger = LoginManager(app)
login_mananger.login_view = 'login'
login_mananger.login_view = 'login'
login_mananger.login_message_category = "info"

db = SQLAlchemy(app)


class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    detail = db.Column(db.String(500))
    price = db.Column(db.Integer, nullable=False)
    discounted_price = db.Column(db.Integer, nullable=False, default=0)
    has_discount = db.Column(db.Boolean, default=False)
    images = db.Column(db.String(500))

    def __repr__(self):
        return f"Post({self.name},{self.price},{self.images})"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(20), nullable=False)
    lastname = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.Integer, nullable=False)
    streetaddress = db.Column(db.String(40), nullable=False)
    city = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(20), nullable=False)
    product = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f"Order({self.id}{self.firstname},{self.email},{self.phone},{self.product})"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(20), nullable=False)
    lastname = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    isSuperAdmin = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"User({self.id}{self.firstname},{self.email},{self.password})"


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    hear_about = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Contact({self.id},{self.first_name} {self.last_name},{self.email},{self.subject})"


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"CartItem({self.id},{self.user_id},{self.product_id},{self.quantity})"
# eSewa Configuration
# eSewa integration for payment processing
# Test product code: EPAYTEST
# Live URL: https://esewa.com.np/epay/main

import hmac
import hashlib
import base64

def generate_esewa_signature(secret_key, message):
    """Generate HMAC SHA256 signature for eSewa"""
    key = secret_key.encode('utf-8')
    message = message.encode('utf-8')
    
    hmac_sha256 = hmac.new(key, message, hashlib.sha256)
    digest = hmac_sha256.digest()
    
    # Convert the digest to a Base64-encoded string
    signature = base64.b64encode(digest).decode('utf-8')
    
    return signature

@app.route('/esewa/request')
@login_required
def esewa_request():
    """Generate eSewa payment request with signature"""
    try:
        # Get order details (you can modify this based on your needs)
        total_amount = request.args.get('amount', 100)  # Get amount from query params
        transaction_uuid = str(uuid.uuid4())
        
        # eSewa configuration
        secret_key = "8gBm/:&EnhH.1/q"  # Test secret key from eSewa docs
        product_code = "EPAYTEST"
        
        # Prepare data for signature
        data_to_sign = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        
        # Generate signature
        signature = generate_esewa_signature(secret_key, data_to_sign)
        
        # Prepare context for template
        context = {
            'amount': total_amount,
            'tax_amount': 0,
            'total_amount': total_amount,
            'transaction_uuid': transaction_uuid,
            'product_code': product_code,
            'signature': signature,
            'success_url': url_for('esewa_success', _external=True),
            'failure_url': url_for('esewa_failure', product_id=transaction_uuid, _external=True)
        }
        
        return render_template('esewa_request.html', **context)
        
    except Exception as e:
        flash(f'Error generating eSewa request: {str(e)}', 'error')
        return redirect(url_for('checkout'))



@app.route('/esewa/success', methods=['GET', 'POST'])
def esewa_success():
    # (Optional) Verify payment with eSewa here

    # Retrieve pending order info from session
    pending = session.get('pending_order')
    print(f"🔍 eSewa success called. Session data: {session}")
    print(f"🔍 Pending order: {pending}")
    if pending:
        # Check if this is a single product order (from buynow) or cart order
        if 'product_id' in pending:
            # Single product order from buynow
            product = Product.query.get(pending['product_id'])
            if product:
                order = Order(
                    firstname=pending['firstname'],
                    lastname=pending['lastname'],
                    email=pending['email'],
                    phone=pending['phone'],
                    streetaddress=pending['streetaddress'],
                    city=pending['city'],
                    country=pending['country'],
                    product=product.id,
                    payment_method='esewa'
                )
                db.session.add(order)
                db.session.commit()
                print(f"✅ eSewa order saved successfully! Order ID: {order.id}")
                print(f"✅ Customer: {order.firstname} {order.lastname}")
                print(f"✅ Product ID: {order.product}")
                print(f"✅ Payment Method: {order.payment_method}")
                
                # Clear cart after successful single product order
                if current_user.is_authenticated:
                    CartItem.query.filter_by(user_id=current_user.id).delete()
                    db.session.commit()
                    print(f"✅ Database cart cleared for user {current_user.id}")
                
                # Always clear session cart
                session['cart'] = {}
                session.modified = True  # Mark session as modified
                print(f"✅ Session cart cleared. Cart count: {len(session.get('cart', {}))}")
        else:
            # Cart order
            cart = pending.get('cart', {})
            for pid, qty in cart.items():
                product = Product.query.get(int(pid))
                if product:
                    order = Order(
                        firstname=pending['firstname'],
                        lastname=pending['lastname'],
                        email=pending['email'],
                        phone=pending['phone'],
                        streetaddress=pending['streetaddress'],
                        city=pending['city'],
                        country=pending['country'],
                        product=product.id,
                        payment_method='esewa'
                    )
                    db.session.add(order)
            db.session.commit()
            print(f"✅ Cart eSewa orders saved successfully!")
            
            # Clear cart after successful order
            if current_user.is_authenticated:
                CartItem.query.filter_by(user_id=current_user.id).delete()
                db.session.commit()
                print(f"✅ Database cart cleared for user {current_user.id}")
            
            # Always clear session cart
            session['cart'] = {}
            session.modified = True  # Mark session as modified
            print(f"✅ Session cart cleared. Cart count: {len(session.get('cart', {}))}")
        
        # Clear the pending order from session
        session.pop('pending_order', None)
    flash("Order Successful with eSewa!", category="success")
    return redirect(url_for('home'))

@app.route('/esewa/failure', methods=['GET', 'POST'])
def esewa_failure():
    product_id = request.args.get('product_id')
    return render_template('payment_failure.html', product_id=product_id)



@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    next_page = request.args.get('next')
    
    if request.method == 'POST':
        # Check if this is an AJAX request from our modals
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            # Handle AJAX login from modals
            email = request.form.get('email')
            password = request.form.get('password')
            next_url = request.form.get('next')
            
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                # Check if user is admin - prevent admin login through customer interface
                if user.isSuperAdmin:
                    return jsonify({'success': False, 'message': 'Admin users must use the admin login portal.'})
                
                login_user(user, remember=True)
                # Clear admin session flag for customer login
                session.pop('admin_login', None)
                
                # Restore user's cart from database to session
                cart_items = CartItem.query.filter_by(user_id=user.id).all()
                if cart_items:
                    session['cart'] = {}
                    for item in cart_items:
                        session['cart'][str(item.product_id)] = item.quantity
                    print(f"Cart restored for user {user.id} with {len(cart_items)} items")
                
                if next_url and next_url.startswith('/'):
                    return jsonify({'success': True, 'redirect': next_url})
                else:
                    return jsonify({'success': True, 'redirect': url_for('home') + '?showFeedback=true'})
            else:
                return jsonify({'success': False, 'message': 'Login unsuccessful. Please check email and password.'})
    
    # Regular form submission (non-AJAX)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            # Check if user is admin - prevent admin login through customer interface
            if user.isSuperAdmin:
                flash('Admin users must use the admin login portal.', 'danger')
                return render_template('login.html', form=form, next=next_page)
            
            login_user(user, remember=True)
            # Clear admin session flag for customer login
            session.pop('admin_login', None)
            
            # Restore user's cart from database to session
            cart_items = CartItem.query.filter_by(user_id=user.id).all()
            if cart_items:
                session['cart'] = {}
                for item in cart_items:
                    session['cart'][str(item.product_id)] = item.quantity
                print(f"Cart restored for user {user.id} with {len(cart_items)} items")
            
            next_post = request.form.get('next')
            if next_post and next_post.startswith('/'):
                return redirect(next_post)
            elif next_page and next_page.startswith('/'):
                return redirect(next_page)
            else:
                return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    
    return render_template('login.html', form=form, next=next_page)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/submit_feedback", methods=['POST'])
@login_required
def submit_feedback():
    # Prevent admin users from submitting feedback as customers
    if current_user.isSuperAdmin and session.get('admin_login'):
        return jsonify({'success': False, 'message': 'Admin users cannot submit customer feedback.'}), 403
    try:
        data = request.get_json()
        
        contact = Contact(
            first_name=data['firstName'],
            last_name=data['lastName'],
            email=data['email'],
            phone=data['phone'],
            subject=data['subject'],
            message=data['message'],
            hear_about=data['hearAbout']
        )
        
        db.session.add(contact)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Feedback submitted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = SignupForm()
    if form.validate_on_submit():
        # Check if the email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash(
                'Email address already in use. Please choose a different one.', 'danger')
            return render_template('signup.html', form=form)

        # Hash the password
        hashed_password = generate_password_hash(form.password.data)

        # Create a new user object
        new_user = User(
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            email=form.email.data,
            password=hashed_password
        )

        # Add the user to the database
        db.session.add(new_user)
        db.session.commit()

        # Flash a success message and redirect to the login page
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html', form=form)


@app.route("/")
def index():
    # Prevent admin users logged in through admin portal from accessing customer interface
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('You are logged in as admin. Please use the admin interface.', 'warning')
        return redirect(url_for('adminViewProducts'))

    newproducts = Product.query.all()
    return render_template("index.html", products=newproducts)


@app.route("/home")
def home():
    # Prevent admin users logged in through admin portal from accessing customer interface
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('You are logged in as admin. Please use the admin interface.', 'warning')
        return redirect(url_for('adminViewProducts'))

    newproducts = Product.query.all()
    return render_template("index.html", products=newproducts)


@app.route("/detail/<int:id>")
def detail(id):
    # Prevent admin users logged in through admin portal from accessing customer interface
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('You are logged in as admin. Please use the admin interface.', 'warning')
        return redirect(url_for('adminViewProducts'))

    product = db.session.query(Product).get(id)
    print(product)
    return render_template("detail.html", product=product)



@app.route("/checkout", methods=['GET', 'POST'])
@login_required
def checkout():
    # Prevent admin users from accessing customer checkout
    if current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot access customer checkout.', 'danger')
        return redirect(url_for('adminViewProducts'))
    cart = get_cart()
    products = []
    total = 0
    to_remove = []
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        try:
            qty = int(qty)
            # Use discounted price if available, otherwise use regular price
            if product.has_discount and product.discounted_price > 0:
                price = int(product.discounted_price)
            else:
                price = int(product.price)
        except (ValueError, TypeError):
            to_remove.append(pid)
            continue
        if product:
            products.append({'product': product, 'qty': qty})
            total += price * qty
    for pid in to_remove:
        del cart[pid]
    session['cart'] = cart

    form = CheckoutForm()
    if form.validate_on_submit():
        payment_method = request.form.get('payment_method')
        if payment_method == 'cod':
            # Save an order for each product in the cart
            for item in products:
                order = Order(
                    firstname=form.firstname.data,
                    lastname=form.lastname.data,
                    email=form.email.data,
                    phone=form.phone.data,
                    streetaddress=form.streetaddress.data,
                    city=form.city.data,
                    country=form.country.data,
                    product=item['product'].id,
                    payment_method='cod'
                )
                db.session.add(order)
            db.session.commit()
            
            # Clear cart after successful order
            if current_user.is_authenticated:
                CartItem.query.filter_by(user_id=current_user.id).delete()
                db.session.commit()
                print(f"✅ Database cart cleared for user {current_user.id}")
            
            # Always clear session cart
            session['cart'] = {}
            session.modified = True  # Mark session as modified
            print(f"✅ Session cart cleared. Cart count: {len(session.get('cart', {}))}")
                
            flash("Order Successful", category="success")
            return redirect(url_for('home'))
        elif payment_method == 'esewa':
            # For eSewa, store user info and cart in session
            session['pending_order'] = {
                'firstname': form.firstname.data,
                'lastname': form.lastname.data,
                'email': form.email.data,
                'phone': form.phone.data,
                'streetaddress': form.streetaddress.data,
                'city': form.city.data,
                'country': form.country.data,
                'cart': cart  # Save the cart dictionary
            }
            print(f"🔍 Pending order stored in session: {session['pending_order']}")
            
            # Generate eSewa payment data and redirect directly to eSewa
            transaction_uuid = str(uuid.uuid4())
            secret_key = "8gBm/:&EnhH.1/q"
            product_code = "EPAYTEST"
            
            # Prepare data for signature
            data_to_sign = f"total_amount={total},transaction_uuid={transaction_uuid},product_code={product_code}"
            signature = generate_esewa_signature(secret_key, data_to_sign)
            
            # Create a simple HTML page that auto-submits to eSewa
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Redirecting to eSewa...</title>
            </head>
            <body>
                <form id="esewaForm" action="https://rc-epay.esewa.com.np/api/epay/main/v2/form" method="POST">
                    <input type="hidden" name="amount" value="{total}">
                    <input type="hidden" name="tax_amount" value="0">
                    <input type="hidden" name="total_amount" value="{total}">
                    <input type="hidden" name="transaction_uuid" value="{transaction_uuid}">
                    <input type="hidden" name="product_code" value="{product_code}">
                    <input type="hidden" name="product_service_charge" value="0">
                    <input type="hidden" name="product_delivery_charge" value="0">
                    <input type="hidden" name="success_url" value="{url_for('esewa_success', _external=True)}">
                    <input type="hidden" name="failure_url" value="{url_for('esewa_failure', product_id=transaction_uuid, _external=True)}">
                    <input type="hidden" name="signed_field_names" value="total_amount,transaction_uuid,product_code">
                    <input type="hidden" name="signature" value="{signature}">
                </form>
                <script>
                    document.getElementById('esewaForm').submit();
                </script>
            </body>
            </html>
            """
            
            return html_content
        else:
            flash("Please select a payment method", category="danger")
            return render_template("checkoutform.html", form=form, products=products, total=total)
    return render_template("checkoutform.html", form=form, products=products, total=total)


def saveProductImage(form_picture, file_name):
    print(file_name)
    _, f_ext = os.path.splitext(form_picture.filename)

    random_id = uuid.uuid4()
    picture = str(random_id)+f_ext
    picture_path = os.path.join(
        app.root_path, "static/images/products", picture)
    form_picture.save(picture_path)
    return f"../static/images/products/{picture}"


@app.route("/addproduct", methods=['GET', 'POST'])
@login_required
def addproduct():
    products = Product.query.all()
    print(products)
    form = AddproductForm()
    if form.validate_on_submit():
        if form.productImage.data:
            picture_file = saveProductImage(
                form.productImage.data, request.form["name"])
            flash("Product Added Successful", category="success")
            product = Product(name=request.form["name"], detail=request.form["description"], price=request.form["price"],
                              discounted_price=request.form["discountPrice"], has_discount=form.checkbox.data, images=picture_file)
            db.session.add(product)
            db.session.commit()
            return redirect(url_for("adminViewProducts"))
        else:
            flash("Product Could not be added", category="danger")
    return render_template("addproductform.html", form=form, products=products)


@app.route("/viewallorders")
@login_required
def viewAllOrders():
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    orders = Order.query.order_by(Order.id.desc()).all()
    print(orders)
    return render_template("viewallorders.html", orders=orders)


@app.route("/delete_order/<int:id>")
@login_required
def delete_order(id):
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    order = Order.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    flash('Order deleted successfully.', 'success')
    return redirect(url_for('viewAllOrders'))


@app.route("/viewcontacts")
@login_required
def viewContacts():
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    return render_template("viewcontacts.html", contacts=contacts)


@app.route("/mark_contact_read/<int:id>")
@login_required
def mark_contact_read(id):
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    contact = Contact.query.get_or_404(id)
    contact.is_read = True
    db.session.commit()
    flash('Message marked as read.', 'success')
    return redirect(url_for('viewContacts'))


@app.route("/delete_contact/<int:id>")
@login_required
def delete_contact(id):
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    contact = Contact.query.get_or_404(id)
    db.session.delete(contact)
    db.session.commit()
    flash('Message deleted successfully.', 'success')
    return redirect(url_for('viewContacts'))


@app.route("/adminviewproduct")
@login_required
def adminViewProducts():
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    products = Product.query.all()
    print(products)
    return render_template("adminviewproduct.html", products=products)


@app.route("/edit/<int:id>", methods=['GET', 'POST'])
@login_required
def edit_product(id):
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    
    product = Product.query.get_or_404(id)
    form = AddproductForm()
    
    if form.validate_on_submit():
        # Update product details
        product.name = form.name.data
        product.detail = form.description.data
        product.price = form.price.data
        product.discounted_price = form.discountPrice.data if form.discountPrice.data else 0
        product.has_discount = form.checkbox.data
        
        # Handle image upload if new image is provided
        if form.productImage.data:
            # Delete old image if it exists
            if product.images and product.images != '../static/images/products/':
                old_file_path = product.images.replace('../', '')
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            
            # Save new image
            picture_file = saveProductImage(form.productImage.data, form.name.data)
            product.images = picture_file
        
        db.session.commit()
        flash("Product Updated Successfully", category="success")
        return redirect(url_for('adminViewProducts'))
    
    elif request.method == 'GET':
        # Pre-populate form with existing data
        form.name.data = product.name
        form.description.data = product.detail
        form.price.data = str(product.price)
        form.discountPrice.data = str(product.discounted_price) if product.discounted_price else ''
        form.checkbox.data = product.has_discount
    
    return render_template("editproductform.html", form=form, product=product)

@app.route("/delete/<int:id>")
def delete(id):
    print(id)
    product = Product.query.filter_by(id=id).first()
    file_path_str = product.images.replace('../', '')
    if os.path.exists(file_path_str):
        os.remove(file_path_str)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('adminViewProducts'))


@app.route("/tryglass/<int:id>")
def tryglass(id):
    print(id)
    product = Product.query.filter_by(id=id).first()
    file_path_str = product.images.replace('../', '')

    image_filenames = os.listdir("static/images/userimages")
    snaps = []
    for filename in image_filenames:
        snaps.append("../static/images/userimages/"+filename)
    image = cv2.imread(file_path_str)
    print(image)
    newproducts = Product.query.all()
    print(newproducts)
    # glass = np.array(bytearray(image),dtype=np.uint8)
    # glass = preprocess(glass)
    try:
        cv2.imwrite('backend/temp_images/glass.jpg', image)
    except:
        pass
    return render_template("tryon.html", products=newproducts, images=snaps, id=id)


@app.route('/video/<int:id>')
def videobyid(id):
    product = Product.query.filter_by(id=id).first()
    file_path_str = product.images.replace('../', '')
    image = cv2.imread(file_path_str)
    try:
        cv2.imwrite('backend/temp_images/glass.jpg', image)
    except:
        pass
    return



@app.route('/video')
def video():

    camera = Capture()

    try:
        glass = cv2.imread('backend/temp_images/glass.jpg')
    except:
        glass = None
    return Response(generate_video(camera, glass=glass, save=None), mimetype='multipart/x-mixed-replace;boundary=frame')


@app.route("/adminlogin", methods=['GET', 'POST'])
def adminlogin():
    if current_user.is_authenticated:
        # Redirect authenticated admin to adminViewProducts
        if current_user.isSuperAdmin:
            return redirect(url_for('adminViewProducts'))
        else:
            flash('You do not have admin privileges.', category='danger')
            return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            if user.isSuperAdmin:
                login_user(user, remember=True)
                # Set session flag to indicate admin login
                session['admin_login'] = True
                return redirect(url_for('adminViewProducts'))
            else:
                flash('You do not have admin privileges.', category="danger")
        else:
            flash('Invalid Credentials', category="danger")

    return render_template("adminlogin.html", title="Login", form=form)


@app.route("/admin_logout")
def admin_logout():
    logout_user()
    # Clear admin session flag
    session.pop('admin_login', None)
    return redirect(url_for('adminlogin'))


@app.route('/user_logout', methods=['GET', 'POST'])
@login_required
def user_logout():
    # Clear session cart only (keep database cart for user)
    session.pop('cart', None)
    # Clear admin session flag
    session.pop('admin_login', None)
    
    logout_user()
    print("User logged out.")
    return redirect(url_for('home'))


@login_mananger.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_cart_count():
    return {'get_cart_count': get_cart_count}


@app.route('/snapshot/')
def Snapshot():
    try:
        glass = cv2.imread('backend/temp_images/glass.jpg')
    except:
        glass = None
    # To Capture
    Capture().filter(glass=glass, save=1)
    image_filenames = os.listdir("static/images/userimages")
    snaps = []
    for filename in image_filenames:
        snaps.append("../static/images/userimages/"+filename)
    print("mf")
    return jsonify(image_urls=snaps)


@app.route('/emotion_feed/')
def emotion_feed():
    def generate():
        with app.app_context():
            emotion_result = cache['emotion']
            if len(emotion_result) > 0:
                positive_emotions = len(
                    [emotion for emotion in emotion_result if emotion == 1])
                negative_emotions = len(
                    [emotion for emotion in emotion_result if emotion == 0])
                cache['emotion'] = []
                if positive_emotions > negative_emotions:
                    resp = 'suggest'
                else:
                    resp = 'change'
            else:
                resp = 'none'
            print("Suggest Result : ", resp)
            yield resp
    return Response(generate(), mimetype='text')

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.get_json().get("message")
    if not user_input:
        return jsonify({"response": "I didn't understand that."})

    sentence = tokenize(user_input)
    X = bag_of_words(sentence, all_words)
    X = X.reshape(1, X.shape[0])
    X = torch.from_numpy(X).to(device)

    output = model(X)
    _, predicted = torch.max(output, dim=1)
    tag = tags[predicted.item()]
    probs = torch.softmax(output, dim=1)
    prob = probs[0][predicted.item()]

    if prob.item() > 0.75:
        for intent in intents["intents"]:
            if tag == intent["tag"]:
                return jsonify({"response": random.choice(intent["responses"])})

    return jsonify({"response": "I'm not sure how to respond to that."})


def get_cart():
    # Always use session cart (simpler and consistent)
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']


def get_cart_count():
    # Always use session cart for display (simpler and consistent)
    return len(session.get('cart', {}))

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    # Prevent admin users from adding items to cart
    if current_user.isSuperAdmin and session.get('admin_login'):
        return jsonify({'success': False, 'message': 'Admin users cannot add items to cart.'}), 403
    product_id = request.form.get('product_id')
    quantity = request.form.get('quantity', 1)
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        flash('Invalid quantity.', 'danger')
        return redirect(request.referrer or url_for('home'))
    
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(request.referrer or url_for('home'))
    
    try:
        price = int(product.price)
    except (ValueError, TypeError):
        flash('Invalid product price.', 'danger')
        return redirect(request.referrer or url_for('home'))
    
    buy_now = request.form.get('buy_now')
    if not product_id:
        flash('No product selected.', 'danger')
        return redirect(request.referrer or url_for('home'))
    
    if quantity < 1:
        quantity = 1
    if quantity > 5:
        quantity = 5
    
    # Always update session cart
    cart = get_cart()
    cart[product_id] = quantity
    session['cart'] = cart
    
    # Also save to database for logged-in users
    if current_user.is_authenticated:
        existing_item = CartItem.query.filter_by(
            user_id=current_user.id, 
            product_id=product_id
        ).first()
        
        if existing_item:
            existing_item.quantity = quantity
        else:
            new_item = CartItem(
                user_id=current_user.id,
                product_id=product_id,
                quantity=quantity
            )
            db.session.add(new_item)
        
        db.session.commit()
    
    flash('Product added/updated in cart!', 'success')
    
    if buy_now:
        return redirect(url_for('checkout'))
    else:
        return redirect(url_for('detail', id=product_id))

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    # Prevent admin users from accessing customer cart
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot access customer cart.', 'danger')
        return redirect(url_for('adminViewProducts'))
    cart = get_cart()
    products = []
    total = 0
    to_remove = []  # List to keep track of bad product ids

    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        try:
            qty = int(qty)
            # Use discounted price if available, otherwise use regular price
            if product.has_discount and product.discounted_price > 0:
                price = int(product.discounted_price)
            else:
                price = int(product.price)
        except (ValueError, TypeError):
            to_remove.append(pid)  # Mark this product for removal
            continue
        if product:
            products.append({'product': product, 'qty': qty})
            total += price * qty

    # Remove any bad items from the cart session
    for pid in to_remove:
        del cart[pid]
    session['cart'] = cart
    if request.method == 'POST':
        # Redirect to checkout page for proper payment processing
        return redirect(url_for('checkout'))
    return render_template('cart.html', products=products, total=total)

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    # Prevent admin users from removing items from customer cart
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot modify customer cart.', 'danger')
        return redirect(url_for('adminViewProducts'))
    product_id = request.form.get('product_id')
    
    # Always remove from session cart
    cart = get_cart()
    if product_id in cart:
        del cart[product_id]
        session['cart'] = cart
    
    # Also remove from database for logged-in users
    if current_user.is_authenticated:
        cart_item = CartItem.query.filter_by(
            user_id=current_user.id, 
            product_id=product_id
        ).first()
        
        if cart_item:
            db.session.delete(cart_item)
            db.session.commit()
    
    flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))

@app.route('/buynow/<int:id>', methods=['GET', 'POST'])
@login_required
def buynow(id):
    # Prevent admin users from using buy now functionality
    if current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot use customer purchase functionality.', 'danger')
        return redirect(url_for('adminViewProducts'))
    product = Product.query.get_or_404(id)
    form = CheckoutForm()
    if form.validate_on_submit():
        payment_method = request.form.get('payment_method')
        if payment_method == 'cod':
            # Save order for this product only
            order = Order(
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                email=form.email.data,
                phone=form.phone.data,
                streetaddress=form.streetaddress.data,
                city=form.city.data,
                country=form.country.data,
                product=product.id,
                payment_method='cod'
            )
            db.session.add(order)
            db.session.commit()
            
            # Clear cart after successful order
            if current_user.is_authenticated:
                CartItem.query.filter_by(user_id=current_user.id).delete()
                db.session.commit()
                print(f"✅ Database cart cleared for user {current_user.id}")
            
            # Always clear session cart
            session['cart'] = {}
            session.modified = True  # Mark session as modified
            print(f"✅ Session cart cleared. Cart count: {len(session.get('cart', {}))}")
            
            flash("Order Successful", category="success")
            return redirect(url_for('home'))
        # For eSewa, store user info and product in session
        session['pending_order'] = {
            'firstname': form.firstname.data,
            'lastname': form.lastname.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'streetaddress': form.streetaddress.data,
            'city': form.city.data,
            'country': form.country.data,
            'product_id': product.id,
            'product_price': product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
        }
        print(f"🔍 Pending order stored in session: {session['pending_order']}")
        
        # Generate eSewa payment data and redirect directly to eSewa
        transaction_uuid = str(uuid.uuid4())
        secret_key = "8gBm/:&EnhH.1/q"
        product_code = "EPAYTEST"
        
        # Use discounted price if available
        payment_amount = product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
        
        # Prepare data for signature
        data_to_sign = f"total_amount={payment_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        signature = generate_esewa_signature(secret_key, data_to_sign)
        
        # Create a simple HTML page that auto-submits to eSewa
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Redirecting to eSewa...</title>
        </head>
        <body>
            <form id="esewaForm" action="https://rc-epay.esewa.com.np/api/epay/main/v2/form" method="POST">
                <input type="hidden" name="amount" value="{payment_amount}">
                <input type="hidden" name="tax_amount" value="0">
                <input type="hidden" name="total_amount" value="{payment_amount}">
                <input type="hidden" name="transaction_uuid" value="{transaction_uuid}">
                <input type="hidden" name="product_code" value="{product_code}">
                <input type="hidden" name="product_service_charge" value="0">
                <input type="hidden" name="product_delivery_charge" value="0">
                <input type="hidden" name="success_url" value="{url_for('esewa_success', _external=True)}">
                <input type="hidden" name="failure_url" value="{url_for('esewa_failure', product_id=transaction_uuid, _external=True)}">
                <input type="hidden" name="signed_field_names" value="total_amount,transaction_uuid,product_code">
                <input type="hidden" name="signature" value="{signature}">
            </form>
            <script>
                document.getElementById('esewaForm').submit();
            </script>
        </body>
        </html>
        """
        
        return html_content
    # Pass a single product as a list for template compatibility
    # Use discounted price if available for total calculation
    total_price = product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
    return render_template("checkoutform.html", form=form, products=[{'product': product, 'qty': 1}], total=total_price)

@app.route("/checkout/<int:id>", methods=['GET', 'POST'])
def checkout_single(id):
    # Prevent admin users from accessing customer checkout
    if current_user.is_authenticated and current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot access customer checkout.', 'danger')
        return redirect(url_for('adminViewProducts'))
    product = Product.query.get_or_404(id)
    form = CheckoutForm()
    if form.validate_on_submit():
        payment_method = request.form.get('payment_method')
        if payment_method == 'cod':
            # Save order for this product only
            order = Order(
                firstname=form.firstname.data,
                lastname=form.lastname.data,
                email=form.email.data,
                phone=form.phone.data,
                streetaddress=form.streetaddress.data,
                city=form.city.data,
                country=form.country.data,
                product=product.id,
                payment_method='cod'
            )
            db.session.add(order)
            db.session.commit()
            
            # Clear cart after successful order
            if current_user.is_authenticated:
                CartItem.query.filter_by(user_id=current_user.id).delete()
                db.session.commit()
                print(f"✅ Database cart cleared for user {current_user.id}")
            
            # Always clear session cart
            session['cart'] = {}
            session.modified = True  # Mark session as modified
            print(f"✅ Session cart cleared. Cart count: {len(session.get('cart', {}))}")
            
            flash("Order Successful", category="success")
            return redirect(url_for('home'))
        # For eSewa, store user info and product in session
        session['pending_order'] = {
            'firstname': form.firstname.data,
            'lastname': form.lastname.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'streetaddress': form.streetaddress.data,
            'city': form.city.data,
            'country': form.country.data,
            'product_id': product.id,
            'product_price': product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
        }
        
        # Generate eSewa payment data and redirect directly to eSewa
        transaction_uuid = str(uuid.uuid4())
        secret_key = "8gBm/:&EnhH.1/q"
        product_code = "EPAYTEST"
        
        # Use discounted price if available
        payment_amount = product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
        
        # Prepare data for signature
        data_to_sign = f"total_amount={payment_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        signature = generate_esewa_signature(secret_key, data_to_sign)
        
        # Create a simple HTML page that auto-submits to eSewa
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Redirecting to eSewa...</title>
        </head>
        <body>
            <form id="esewaForm" action="https://rc-epay.esewa.com.np/api/epay/main/v2/form" method="POST">
                <input type="hidden" name="amount" value="{payment_amount}">
                <input type="hidden" name="tax_amount" value="0">
                <input type="hidden" name="total_amount" value="{payment_amount}">
                <input type="hidden" name="transaction_uuid" value="{transaction_uuid}">
                <input type="hidden" name="product_code" value="{product_code}">
                <input type="hidden" name="product_service_charge" value="0">
                <input type="hidden" name="product_delivery_charge" value="0">
                <input type="hidden" name="success_url" value="{url_for('esewa_success', _external=True)}">
                <input type="hidden" name="failure_url" value="{url_for('esewa_failure', product_id=transaction_uuid, _external=True)}">
                <input type="hidden" name="signed_field_names" value="total_amount,transaction_uuid,product_code">
                <input type="hidden" name="signature" value="{signature}">
            </form>
            <script>
                document.getElementById('esewaForm').submit();
            </script>
        </body>
        </html>
        """
        
        return html_content
    # Pass a single product as a list for template compatibility
    # Use discounted price if available for total calculation
    total_price = product.discounted_price if product.has_discount and product.discounted_price > 0 else product.price
    return render_template("checkoutform.html", form=form, products=[{'product': product, 'qty': 1}], total=total_price)


@app.route('/get_esewa_signature')
@login_required
def get_esewa_signature():
    """Generate eSewa signature for modal payment"""
    try:
        amount = request.args.get('amount')
        transaction_uuid = request.args.get('transaction_uuid')
        
        if not amount or not transaction_uuid:
            return jsonify({'error': 'Missing parameters'}), 400
        
        # eSewa configuration
        secret_key = "8gBm/:&EnhH.1/q"
        product_code = "EPAYTEST"
        
        # Prepare data for signature
        data_to_sign = f"total_amount={amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        
        # Generate signature using your existing function
        signature = generate_esewa_signature(secret_key, data_to_sign)
        
        return jsonify({
            'signature': signature,
            'success_url': url_for('esewa_success', _external=True),
            'failure_url': url_for('esewa_failure', product_id=transaction_uuid, _external=True)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/order-history')
@login_required
def order_history():
    # Prevent admin users from accessing customer order history
    if current_user.isSuperAdmin and session.get('admin_login'):
        flash('Admin users cannot access customer order history.', 'danger')
        return redirect(url_for('adminViewProducts'))
    
    orders = Order.query.filter_by(email=current_user.email).order_by(Order.id.desc()).all()
    
    # Fetch product data for each order
    orders_with_products = []
    for order in orders:
        product = Product.query.get(order.product)
        orders_with_products.append({
            'order': order,
            'product': product
        })
    
    return render_template('order_history.html', orders_with_products=orders_with_products)

@app.route('/delete_user_order/<int:id>', methods=['DELETE'])
@login_required
def delete_user_order(id):
    # Prevent admin users from deleting customer orders through this route
    if current_user.isSuperAdmin and session.get('admin_login'):
        return jsonify({'success': False, 'message': 'Admin users cannot delete customer orders through this interface.'}), 403
    try:
        # Find the order and verify it belongs to the current user
        order = Order.query.filter_by(id=id, email=current_user.email).first()
        
        if not order:
            return jsonify({'success': False, 'message': 'Order not found or access denied'}), 404
        
        # Delete the order
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while deleting the order'}), 500

if __name__ == "__main__":
    app.run(debug=True)
