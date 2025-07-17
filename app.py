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

with open('intents.json', 'r') as json_data:
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
    product = db.Column(db.Integer, db.ForeignKey(
        'product.id'), nullable=False)

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
# Khalti Configuration
# Get your actual Khalti API credentials from: https://khalti.com/merchant/account/apikey/
# For development, you can use test credentials
# For production, use live credentials

# IMPORTANT: You need to replace these with real Khalti API credentials
# The current values are placeholders and will cause "Invalid token" errors
# KHALTI_TEST_PUBLIC_KEY = os.environ.get('KHALTI_PUBLIC_KEY', "test_public_key_dc74e0fd57cb46cd93832aee0a390234")
# KHALTI_TEST_SECRET_KEY = os.environ.get('KHALTI_SECRET_KEY', "test_secret_key_...")  # Replace with your actual secret key
# KHALTI_VERIFY_URL = "https://khalti.com/api/v2/payment/verify/"

# For testing purposes, you can temporarily use these test credentials:
# KHALTI_TEST_PUBLIC_KEY = "test_public_key_dc74e0fd57cb46cd93832aee0a390234"
# KHALTI_TEST_SECRET_KEY = "test_secret_key_..."  # This needs to be a real secret key

# @app.route('/initiate-khalti', methods=['POST'])
# def initiate_khalti():
#     try:
#         product_id = request.form.get('product_id')
#         product = Product.query.get(product_id)
        
#         if not product:
#             return jsonify({"success": False, "message": "Product not found"}), 404

#         # Check if we're using placeholder credentials
#         if KHALTI_TEST_SECRET_KEY == "test_secret_key_...":
#             return jsonify({
#                 "success": False, 
#                 "message": "Khalti API credentials not configured. Please set up real Khalti API credentials. See KHALTI_SETUP.md for instructions."
#             }), 400

#         payload = {
#             "return_url": url_for('payment_success', _external=True),
#             "website_url": url_for('home', _external=True),
#             "amount": product.price * 100,  # Convert to paisa
#             "purchase_order_id": f"order_{int(time.time())}",
#             "purchase_order_name": product.name,
#             "customer_info": {
#                 "name": request.form.get('firstname') + " " + request.form.get('lastname'),
#                 "email": request.form.get('email'),
#                 "phone": request.form.get('phone')
#             }
#         }
        
#         headers = {
#             "Authorization": f"Key {KHALTI_TEST_SECRET_KEY}",
#             "Content-Type": "application/json"
#         }
        
#         response = requests.post(
#             "https://a.khalti.com/api/v2/epayment/initiate/",
#             json=payload,
#             headers=headers
#         )
        
#         if response.status_code == 200:
#             return jsonify({
#                 "success": True,
#                 "payment_url": response.json()['payment_url']
#             })
        
#         # Handle specific error cases
#         error_detail = response.json().get('detail', 'Payment initiation failed')
#         if "Invalid token" in error_detail:
#             return jsonify({
#                 "success": False,
#                 "message": "Invalid Khalti API credentials. Please check your KHALTI_SECRET_KEY configuration."
#             }), 400
        
#         return jsonify({
#             "success": False,
#             "message": error_detail
#         }), 400
        
#     except Exception as e:
#         return jsonify({"success": False, "message": str(e)}), 500

@app.route('/payment/success')
def payment_success():
    # This endpoint is called by Khalti after successful payment
    # You can add logic here to handle the success callback
    return render_template('payment_success.html')

@app.route('/payment/verify', methods=['POST'])
def verify_payment():
    try:
        # Get the pidx from the callback (Khalti sends this after payment)
        pidx = request.form.get('pidx')
        if not pidx:
            return jsonify({"success": False, "message": "Missing pidx parameter"}), 400

        # Verify payment with Khalti
        response = requests.post(
            KHALTI_VERIFY_URL,
            data={"pidx": pidx},
            headers={"Authorization": f"Key {KHALTI_TEST_SECRET_KEY}"},
            timeout=10
        )

        response_data = response.json()
        
        if response.status_code == 200:
            # Payment was successful - create order
            # Note: In a real implementation, you might want to store order details in session
            # or pass them through the return_url as parameters
            
            # For now, we'll create a basic order with available data
            order = Order(
                firstname=response_data.get('user', {}).get('name', '').split(' ')[0] or 'Customer',
                lastname=' '.join(response_data.get('user', {}).get('name', '').split(' ')[1:]) or 'Name',
                email=response_data.get('user', {}).get('email', 'customer@example.com'),
                phone=response_data.get('user', {}).get('mobile', '0000000000'),
                streetaddress=request.form.get('streetaddress', 'N/A'),
                city=request.form.get('city', 'N/A'),
                country=request.form.get('country', 'Nepal'),
                product=request.form.get('product_id', 1)  # Default to product ID 1 if not provided
            )
            db.session.add(order)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Payment verified successfully",
                "data": response_data
            })
        else:
            return jsonify({
                "success": False,
                "message": response_data.get('detail', 'Payment verification failed'),
                "khalti_response": response_data
            }), 400
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Verification error: {str(e)}",
            "error_type": type(e).__name__
        }), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    next_page = request.args.get('next')
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=True)
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
    newproducts = Product.query.all()
    return render_template("index.html", products=newproducts)


@app.route("/home")
def home():

    newproducts = Product.query.all()
    return render_template("index.html", products=newproducts)


@app.route("/detail/<int:id>")
def detail(id):
    product = db.session.query(Product).get(id)
    print(product)
    return render_template("detail.html", product=product)



@app.route("/checkout", methods=['GET', 'POST'])
@login_required
def checkout():
    cart = get_cart()
    products = []
    total = 0
    to_remove = []
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        try:
            qty = int(qty)
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
                product=item['product'].id
            )
            db.session.add(order)
        db.session.commit()
        session['cart'] = {}
        flash("Order Successful", category="success")
        return redirect(url_for('home'))
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

    orders = Order.query.all()
    print(orders)
    return render_template("viewallorders.html", orders=orders)


@app.route("/adminviewproduct")
@login_required
def adminViewProducts():
    if not current_user.isSuperAdmin:
        flash('Access denied. Admins only.', category='danger')
        return redirect(url_for('home'))
    products = Product.query.all()
    print(products)
    return render_template("adminviewproduct.html", products=products)


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
                return redirect(url_for('adminViewProducts'))
            else:
                flash('You do not have admin privileges.', category="danger")
        else:
            flash('Invalid Credentials', category="danger")

    return render_template("adminlogin.html", title="Login", form=form)


@app.route("/admin_logout")
def admin_logout():
    logout_user()
    return redirect(url_for('adminlogin'))


@app.route('/user_logout', methods=['GET', 'POST'])
@login_required
def user_logout():
    logout_user()
    print("User logged out.")
    return redirect(url_for('home'))


@login_mananger.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = request.form.get('quantity', 1)
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        flash('Invalid quantity.', 'danger')
        return redirect(request.referrer or url_for('home'))
    product = Product.query.get(product_id)
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
    cart = get_cart()
    cart[product_id] = quantity
    session['cart'] = cart
    flash('Product added/updated in cart!', 'success')
    if buy_now:
        return redirect(url_for('checkout'))
    else:
        return redirect(url_for('detail', id=product_id))

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    cart = get_cart()
    products = []
    total = 0
    to_remove = []  # List to keep track of bad product ids

    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        try:
            qty = int(qty)
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
        # Handle checkout logic here (same form as add_to_cart)
        # You can process the order, clear the cart, etc.
        flash('Order placed successfully!', 'success')
        session['cart'] = {}
        return redirect(url_for('home'))
    return render_template('cart.html', products=products, total=total)

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    product_id = request.form.get('product_id')
    cart = get_cart()
    if product_id in cart:
        del cart[product_id]
        session['cart'] = cart
        flash('Item removed from cart.', 'success')
    return redirect(url_for('cart'))

@app.route('/buynow/<int:id>', methods=['GET', 'POST'])
@login_required
def buynow(id):
    product = Product.query.get_or_404(id)
    form = CheckoutForm()
    if form.validate_on_submit():
        # Save order for this product only
        order = Order(
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            email=form.email.data,
            phone=form.phone.data,
            streetaddress=form.streetaddress.data,
            city=form.city.data,
            country=form.country.data,
            product=product.id
        )
        db.session.add(order)
        db.session.commit()
        flash("Order Successful", category="success")
        return redirect(url_for('home'))
    # Pass a single product as a list for template compatibility
    return render_template("checkoutform.html", form=form, products=[{'product': product, 'qty': 1}], total=product.price)

@app.route("/checkout/<int:id>", methods=['GET', 'POST'])
def checkout_single(id):
    product = Product.query.get_or_404(id)
    form = CheckoutForm()
    if form.validate_on_submit():
        # Save order for this product only
        order = Order(
            firstname=form.firstname.data,
            lastname=form.lastname.data,
            email=form.email.data,
            phone=form.phone.data,
            streetaddress=form.streetaddress.data,
            city=form.city.data,
            country=form.country.data,
            product=product.id
        )
        db.session.add(order)
        db.session.commit()
        flash("Order Successful", category="success")
        return redirect(url_for('home'))
    # Pass a single product as a list for template compatibility
    return render_template("checkoutform.html", form=form, products=[{'product': product, 'qty': 1}], total=product.price)


if __name__ == "__main__":
    app.run(debug=True)
