from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory, make_response, flash
from flask_sqlalchemy import SQLAlchemy
import re
import os
import random
from sqlalchemy import exc
import requests
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from jose import jwt, JWTError
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth
from credentials import *
from flask_mail import Mail, Message
from bs4 import BeautifulSoup
import google.generativeai as genai
import markdown
from youtube_search import YoutubeSearch
from googleapiclient.discovery import build

app = Flask(__name__)
""" app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:Ssd11012004+-=@localhost:3306/food_delivery" """
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///food_delivery.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'soham.daddikar22@spit.ac.in'
app.config['MAIL_PASSWORD'] = '2022300018'
app.config['MAIL_DEFAULT_SENDER'] = 'soham.daddikar22@spit.ac.in'
app.secret_key = '964e7a234803207c59413ba2d8a72f7b9417115f18945e3fce970cf4e58eadef'
GEMINI_API_KEY = "AIzaSyAK2WsGSgro8ySMQsZWg4Q55ZT_rOAblOg"
YOUTUBE_API_KEY = "AIzaSyCFgSOZz8R-bog8Thj_midN4wxxPPWA0Ys"
WEATHER_API_KEY = "997060352864d28d4fdb7259b8b0eb81"
db = SQLAlchemy(app)
mail = Mail(app)

oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=CLIENT_ID,  # Replace with your actual Google client ID
    client_secret=CLIENT_SECRET,  # Replace with your actual Google client secret
    server_metadata_uri = 'https://accounts.google.com/.well-known/openid-configuration',
    authorize_url='https://accounts.google.com/o/oauth2/auth',  # Explicitly set the authorize URL
    authorize_params=None,
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    refresh_token_url=None,
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'},
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo'
)


SECRET_KEY = '964e7a234803207c59413ba2d8a72f7b9417115f18945e3fce970cf4e58eadef'
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class User(db.Model):
    __tablename__ = 'user'
    
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_name = db.Column(db.String(255), nullable = True)
    user_password = db.Column(db.String(255), nullable = True)
    user_mail = db.Column(db.String(255), unique = True, nullable = True)
    user_city = db.Column(db.String(255), nullable = True)
    user_state = db.Column(db.String(255), nullable = True)
    user_country = db.Column(db.String(255), nullable = True)
    user_extra_address = db.Column(db.String(1024), nullable = True)
    profile_image = db.Column(db.String(255))
    
class Item(db.Model):
    __tablename__ = 'item'
    
    item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_name = db.Column(db.String(255), nullable = False)
    item_price = db.Column(db.Integer, nullable = False)
    item_category = db.Column(db.Boolean, nullable = False)
    item_quantity = db.Column(db.Integer, nullable = False)
    item_image = db.Column(db.String(800), nullable = True)
    item_ingredients = db.Column(db.String(4000), nullable = True)
    item_steps = db.Column(db.String(4000), nullable = True)
    item_nutrients = db.Column(db.String(4000), nullable = True)
    item_timing = db.Column(db.String(900), nullable = True)
    item_youtube = db.Column(db.String(800), nullable = True)
    
class Cart(db.Model):
    __tablename__ = 'cart'
    
    cart_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cart_name = db.Column(db.String(255), nullable = False)
    cart_price = db.Column(db.Integer, nullable = False)
    cart_category = db.Column(db.Boolean, nullable = False)
    cart_quantity = db.Column(db.Integer, nullable = False)
    cart_image = db.Column(db.String(800), nullable = True)
    
with app.app_context():
    db.create_all()
    
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    weather_data = response.json()
    
    if response.status_code == 200:
        main_weather = weather_data['weather'][0]['main']
        return main_weather
    else:
        return None


def remove_markdown(text):
    # Convert markdown to HTML
    html = markdown.markdown(text)
    # Parse the HTML to strip tags
    soup = BeautifulSoup(html, "html.parser")
    # Get the plain text
    plain_text = soup.get_text()
    # Split into lines, remove extra spaces from each line, and then rejoin with line breaks
    cleaned_lines = [line.strip() for line in plain_text.splitlines() if line.strip()]  # Removes empty lines too
    return '\n'.join(cleaned_lines)  # Join the cleaned lines with line breaks

def suggest_food_based_on_weather(weather):
    prompt = f"Suggest me an Indian dish for {weather} weather."
    response = model.generate_content(prompt)
    
    if hasattr(response, 'text'):
        clean_text = remove_markdown(response.text)  # Ensure clean_text is a single string
        return clean_text
    return "No suggestion found."

# Function to scrape ingredients (Error Handling)
def respond_ingredients(query):
    prompt = f'Give me ingredients to make {query}. I want it in point format and remove markdown formatting.'
    
    response = model.generate_content(prompt)
    
    if hasattr(response, 'text'):
        clean_text = remove_markdown(response.text)
        
        return clean_text.splitlines()
    return []

# Function to scrape steps (Error Handling)
def respond_steps(query):
    prompt = f'Give me steps to make {query}. I want it in point format and remove markdown formatting.'
    
    response = model.generate_content(prompt)
    
    if hasattr(response, 'text'):
        clean_text = remove_markdown(response.text)
        
        return clean_text.splitlines()
    return []

# Function to scrape nutrients (Error Handling)
def respond_nutrients(query):
    prompt = f'Give me nutrients that are in {query} like proteins, calories, vitamins count in it. I want it in point format and remove markdown formatting.'
    
    response = model.generate_content(prompt)
    
    if hasattr(response, 'text'):
        clean_text = remove_markdown(response.text)
        
        return clean_text.splitlines()
    
    return []

# Function to scrape timing information 
def respond_timing(query):
    prompt = f'Give me time needed for each step of making {query}. I want it in point format and remove markdown formatting.'
    
    response = model.generate_content(prompt)
    
    if hasattr(response, 'text'):
        clean_text = remove_markdown(response.text)
        
        return clean_text.splitlines()
    
    return []

# Function to scrape wikipedia image
def scrape_image_from_wikipedia(dish_name):
    # Create the Wikipedia URL for the specific dish
    url = f'https://en.wikipedia.org/wiki/{dish_name.replace(" ", "_")}'

    # Send a GET request to the Wikipedia page
    response = requests.get(url)
    
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the infobox table
        infobox = soup.find('table', class_='infobox hrecipe adr')

        if infobox:
            # Find the image within the infobox
            image_tag = infobox.find('img')
            if image_tag:
                # Construct the full image URL
                image_url = f"https:{image_tag['src']}"  # Add 'https:' to the src
                return image_url
            else:
                print("Image not found in the infobox.")
        else:
            print("Infobox not found.")
    else:
        print(f"Failed to fetch the Wikipedia page, status code: {response.status_code}")

    return None

# Function to scrape the recipe data 
# 1) Ingredients
# 2) Steps
# 3) Image
# 4) Nutrients
# 5) Time
def scrape_recipe(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Scraping the image
    image_section = soup.find('div', class_='article-image')
    image_url = ""
    if image_section:  # Check if image_section is not None
        img_tag = image_section.find('img')
        if img_tag and 'src' in img_tag.attrs:  # Ensure img_tag has 'src' attribute
            image_url = img_tag['src']

    # Scraping ingredients
    ingredients = []
    ingredients_section = soup.find('h2', string='Ingredients')
    if ingredients_section:
        ingredients_section = ingredients_section.find_next('ul')
        if ingredients_section:
            for li in ingredients_section.find_all('li'):
                ingredients.append(li.get_text(strip=True))

    # Scraping steps
    method = []
    method_section = soup.find('h2', string='Method')
    if method_section:
        method_section = method_section.find_next('ol')
        if method_section:
            for li in method_section.find_all('li'):
                method.append(li.get_text(strip=True))

    return {
        "image": image_url,
        "ingredients": ingredients,
        "method": method
    }
    
def scrape_nutrients(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    nutrients = {}
    nutrition_summary = soup.find('div', class_='factPanel')

    if nutrition_summary:
        nutrient_rows = nutrition_summary.find_all('td', class_='fact')
        for nutrient in nutrient_rows:
            title = nutrient.find('div', class_='factTitle').get_text(strip=True)
            value = nutrient.find('div', class_='factValue').get_text(strip=True)
            nutrients[title] = value

    return nutrients if nutrients else {}

def get_youtube_video(query):
    # Build the YouTube API service
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Perform the search using the YouTube API
    request = youtube.search().list(
        part='snippet',
        q=query,
        maxResults=1,  # Set maxResults to 1 to get the top result
        type='video'   # Ensure we're searching for videos only
    )
    response = request.execute()
    
    # Parse the response and extract video information
    if response['items']:
        video_id = response['items'][0]['id']['videoId']
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        return video_url
    else:
        return None
    
def validate_input(text):
    return re.match("^[A-Za-z ]+$", text) is not None
    
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("user_email")
        if email is None:
            raise JWTError
        return email
    except JWTError:
        return None

def get_jwt_from_request():
    auth_header = request.headers.get("Authorization")
    if auth_header:
        return auth_header.split(" ")[1]
    return None
    
@app.route('/')
def home():
    token = request.cookies.get('access_token')
    if not token:
        return render_template('home.html')

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('home.html')
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('home.html')

    # Pass the user's name to the template
    return render_template('home.html', user_name=user.user_name)

@app.route('/loading/<string:recipe_name>')# loading page
def loading(recipe_name):
    return redirect(url_for('get_recipe', recipe_name=recipe_name))

@app.route('/recipe/<string:recipe_name>', methods = ['GET', 'POST'])
def get_recipe(recipe_name):
    existing_recipe = Item.query.filter_by(item_name=recipe_name).first()

    if existing_recipe:
        # If the recipe exists, split ingredients, steps, and nutrients by '\n'
        recipe_data = {
            'image': existing_recipe.item_image,
            'ingredients': existing_recipe.item_ingredients.split('\n') if existing_recipe.item_ingredients else [],
            'method': existing_recipe.item_steps.split('\n') if existing_recipe.item_steps else [],
            'nutrients': existing_recipe.item_nutrients.split('\n') if existing_recipe.item_nutrients else [],
            'timing': existing_recipe.item_timing.split('\n') if existing_recipe.item_timing else [],
        }
        display_category = "Non-Veg" if existing_recipe.item_category == 1 else "Veg"
        
        weather = get_weather("Mumbai")
        
        food_suggestion = suggest_food_based_on_weather(weather)
        
        recipe_data['suggest'] = food_suggestion.split('.')
        
        token = request.cookies.get('access_token')
        if not token:
            return render_template('scrape_test.html', recipe_data=recipe_data, recipe_name=existing_recipe.item_name, display_category=display_category, video_url = existing_recipe.item_youtube, food_suggestion = food_suggestion)

        # Verify and decode the token
        email = verify_access_token(token)
        if not email:
            return render_template('scrape_test.html', recipe_data=recipe_data, recipe_name=existing_recipe.item_name, display_category=display_category, video_url = existing_recipe.item_youtube, food_suggestion = food_suggestion)
        
        # Fetch user details from the database
        user = User.query.filter_by(user_mail=email).first()
        if not user:
            return render_template('scrape_test.html', recipe_data=recipe_data, recipe_name=existing_recipe.item_name, display_category=display_category, video_url = existing_recipe.item_youtube, food_suggestion = food_suggestion)
        
        return render_template('scrape_test.html', recipe_data=recipe_data, recipe_name=existing_recipe.item_name, display_category=display_category, video_url = existing_recipe.item_youtube, food_suggestion = food_suggestion, user_name = user.user_name)
    
    
    recipe_url = f'https://www.sanjeevkapoor.com/Recipe/{recipe_name.replace(" ", "-")}.html'
    nutrients_url = f'https://www.fatsecret.com/calories-nutrition/trader-joes/{recipe_name.replace(" ", "-")}'
    
    #recipe_url = 'https://www.sanjeevkapoor.com/Recipe/Paneer-Tikka.html'
    #nutrients_url = 'https://www.fatsecret.com/calories-nutrition/trader-joes/paneer-tikka-masala'
    
    non_veg_keywords = ['chicken', 'fish', 'mutton', 'shrimp', 'egg']
    is_non_veg = any(keyword.lower() in recipe_name.lower() for keyword in non_veg_keywords)
    veg_status = 1 if is_non_veg else 0
    display_category = "Veg"
    if veg_status == 1:
        display_category = "Non-Veg"

    # Scrape the data
    recipe_data = scrape_recipe(recipe_url)
    nutrients_data = scrape_nutrients(nutrients_url)
    generated_timing = respond_timing(recipe_name)
    recipe_data['timing'] = generated_timing
    
    recipe_data['nutrients'] = nutrients_data
    
    weather = get_weather("Mumbai")
        
    food_suggestion = suggest_food_based_on_weather(weather)
    
    recipe_data['suggest'] = food_suggestion.split('.')
    
    if not recipe_data['image']:
        recipe_data['image'] = scrape_image_from_wikipedia(recipe_name)
        
        print(recipe_data['image'])
        
    if not recipe_data['ingredients'] or not recipe_data['method'] or not recipe_data['nutrients']:
        generated_ingredients = respond_ingredients(recipe_name)
        generated_steps = respond_steps(recipe_name)
        generated_nutrients = respond_nutrients(recipe_name)
        recipe_data['ingredients'] = recipe_data['ingredients'] or generated_ingredients
        recipe_data['method'] = recipe_data['method'] or generated_steps
        recipe_data['nutrients'] = recipe_data['nutrients'] or generated_nutrients
        
    prompt = f"how to make {recipe_name} recipe"
    original_video_url = get_youtube_video(prompt)
    
    if "youtube.com/watch?v=" in original_video_url:
        video_id = original_video_url.split("v=")[-1]
        video_url = f"https://www.youtube.com/embed/{video_id}"
    else:
        video_url = original_video_url
        
    item_name = recipe_name
    item_category = veg_status
    item_quantity = random.randint(10, 50)
    item_image = recipe_data['image'] if recipe_data['image'] else None
    item_ingredients = '\n'.join(recipe_data['ingredients']) if recipe_data['ingredients'] else None
    item_steps = '\n'.join(recipe_data['method']) if recipe_data['method'] else None
    item_nutrients = '\n'.join(recipe_data['nutrients']) if recipe_data['nutrients'] else None
    item_timing = '\n'.join(recipe_data['timing']) if recipe_data['timing'] else None
    item_youtube = video_url
    item_price = random.randint(5, 20)
    
    new_item = Item(item_name = item_name, item_price = item_price, item_category = item_category, item_quantity = item_quantity, item_image = item_image, item_ingredients = item_ingredients, item_steps = item_steps, item_nutrients = item_nutrients, item_timing = item_timing, item_youtube = item_youtube)
    
    db.session.add(new_item)
    db.session.commit()    
    
    token = request.cookies.get('access_token')
    if not token:
        return render_template('scrape_test.html', recipe_data = recipe_data, recipe_name = recipe_name, display_category = display_category, video_url = video_url, food_suggestion = food_suggestion)

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('scrape_test.html', recipe_data = recipe_data, recipe_name = recipe_name, display_category = display_category, video_url = video_url, food_suggestion = food_suggestion)
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('scrape_test.html', recipe_data = recipe_data, recipe_name = recipe_name, display_category = display_category, video_url = video_url, food_suggestion = food_suggestion)

    return render_template('scrape_test.html', recipe_data = recipe_data, recipe_name = recipe_name, display_category = display_category, video_url = video_url, food_suggestion = food_suggestion, user_name = user.user_name)

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/reset')
def reset():
    return render_template('password.html')

@app.route('/special')
def special():
    token = request.cookies.get('access_token')
    if not token:
        return render_template('special.html')

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('special.html')
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('special.html')
    
    return render_template('special.html', user_name=user.user_name)

@app.route('/complete_profile', methods = ['GET', 'POST'])
def profile_completion():
    token = request.cookies.get('access_token')
    
    if not token:
        return redirect(url_for('login'))
    
    email = verify_access_token(token)
    
    if not email:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(user_mail=email).first()
    
    if not user:
        return redirect(url_for('signup'))
    
    
    if request.method == 'POST':
        user_city = request.form['city']
        user_state = request.form['state']
        user_country = request.form['country']
        extra_address = request.form['address']
        
        if not validate_input(user_city) or not validate_input(user_state) or not validate_input(user_country) or not validate_input(extra_address):
            return "Invalid input. Please ensure that no numbers or special characters are used in city, state, country or the specific address", 400
        
        user.user_city = user_city
        user.user_state = user_state
        user.user_country = user_country
        user.user_extra_address = extra_address
        
        db.session.commit()
        
        return "Profile updated successfully"
    
    return render_template('profile_completion.html')

@app.route('/login/google')
def google_login():
    try:
        redirect_uri = url_for('authorize_google', _external = True)
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        app.logger.error(f"Error during login:{str(e)}")
        return "Error ocurred during login", 500
    
    
@app.route('/auth/callback')
def authorize_google():
    token = google.authorize_access_token()
    userinfo_endpoint = google.server_metadata['userinfo_endpoint']
    resp = google.get(userinfo_endpoint)
    user_info = resp.json()
    email = user_info['email']
    name = user_info.get('name')
    
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        user = User(user_mail = email, user_name = name)
        db.session.add(user)
        db.session.commit()
        
    # Generate JWT token with the user's email
    access_token = create_access_token({"user_email": user.user_mail})
    
    # Set the access token in an HTTP-only cookie
    response = make_response(redirect(url_for('profile_completion')))
    response.set_cookie('access_token', access_token, httponly=True)
    
    return response
    
@app.route('/login-data', methods = ['GET', 'POST'])
def login_data():
    if request.method == 'POST':
        email = request.form['mail']
        password = request.form['pass']
        
        user = User.query.filter_by(user_mail=email).first()
    
        if user:
            if user.user_password:
                if check_password_hash(user.user_password, password):
                    access_token = create_access_token({"user_email": user.user_mail})
                    response = make_response(jsonify({"status": "success", 'access_token': access_token}))
                    response.set_cookie('access_token', access_token, httponly=True)
                    return response
                else:
                    return jsonify({'status': 'error', 'message': 'Incorrect password.'})
                
            else:
                return jsonify({'status': 'error', 'message': 'Password not set. Please log in via Google OAuth.'})
        else:
            return jsonify({'status': 'error', 'message': 'No account found with that email.'})
        
@app.route('/signup-data', methods = ['GET', 'POST'])
def signup_data():
    if request.method == 'POST':
        username = request.form['user_name']
        email = request.form['mail']
        password = request.form['pass']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        extra_address = request.form['extra']

        # Input validation
        if not validate_input(username) or not validate_input(city) or not validate_input(state) or not validate_input(country):
            return "Invalid input. Please ensure that no numbers or special characters are used in the required fields.", 400

        # Optional field validation (if provided)
        if extra_address and not validate_input(extra_address):
            return "Invalid input in the extra address field. Please ensure that no numbers or special characters are used.", 400

        # If user exists 
        existing_user = User.query.filter_by(user_mail=email).first()
        if existing_user:
            return "User with this email already exists. Please login."
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_user = User(
            user_name=username,
            user_password=hashed_password,
            user_mail=email,
            user_city=city,
            user_state=state,
            user_country=country,
            user_extra_address=extra_address if extra_address else None
        )

        db.session.add(new_user)
        db.session.commit()

        return "Success"

    return render_template('signup.html')

@app.route('/reset-password', methods = ['GET', 'POST', 'PUT'])
def reset_password():
    if request.method == 'POST' or request.method == 'PUT':
        email = request.form.get('email')
        new_password = request.form.get('newPassword')
        
        user = User.query.filter_by(user_mail=email).first()

        if user:
            user.user_password = new_password
            db.session.commit()
            
            return "Password reset successful"
        else:
            return "Email not found. Please check your email and try again."
        
    return render_template('password.html')

@app.route('/cart', methods = ['GET', 'POST'])
def cart():
    token = request.cookies.get('access_token')
    if not token:
        return render_template('trial_cart.html')

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('trial_cart.html')
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('trial_cart.html')
    
    return render_template('trial_cart.html', user_name = user.user_name)

@app.route('/update-cart', methods=['POST'])
def update_cart_page():
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        action = data.get('action')
        
        # Find the cart item
        cart_item = Cart.query.get(item_id)
        
        if not cart_item:
            return jsonify({
                'success': False,
                'message': 'Cart item not found'
            }), 404
        
        # Update quantity based on action
        if action == 'increase':
            cart_item.cart_quantity += 1
        elif action == 'decrease':
            if cart_item.cart_quantity > 1:  # Prevent quantity from going below 1
                cart_item.cart_quantity -= 1
            else:
                return jsonify({
                    'success': False,
                    'message': 'Quantity cannot be less than 1'
                }), 400
        
        # Save changes
        db.session.commit()
        
        # Return updated item details
        return jsonify({
            'success': True,
            'data': {
                'cart_id': cart_item.cart_id,
                'cart_name': cart_item.cart_name,
                'cart_quantity': cart_item.cart_quantity,
                'is_nonveg': cart_item.cart_category,  # True for non-veg, False for veg
                'cart_image': cart_item.cart_image
            }
        })
        
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/remove-from-cart', methods=['POST'])
def remove_from_cart():
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        
        # Find the cart item
        cart_item = Cart.query.get(item_id)
        
        if not cart_item:
            return jsonify({
                'success': False,
                'message': 'Cart item not found'
            }), 404
        
        # Remove the item
        db.session.delete(cart_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item removed successfully'
        })
        
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Route to get cart items (useful for displaying the cart)
@app.route('/get-cart-items', methods=['GET'])
def get_cart_items():
    try:
        cart_items = Cart.query.all()
        
        items = []
        for item in cart_items:
            items.append({
                'cart_id': item.cart_id,
                'cart_name': item.cart_name,
                'cart_quantity': item.cart_quantity,
                'cart_category': item.cart_category,  # True for non-veg, False for veg
                'cart_image': item.cart_image,  # Ensure price is included for subtotal calculations
                'type': 'Non-Vegetarian' if item.cart_category else 'Vegetarian',
                'price': item.cart_price
            })
        
        return jsonify({
            'success': True,
            'data': {
                'items': items,
                'total_items': len(items)
            }
        })
        
    except exc.SQLAlchemyError:
        return jsonify({
            'success': False,
            'message': 'Database error occurred'
        }), 500
        
@app.route('/checkout')
def checkout():
    token = request.cookies.get('access_token')
    if not token:
        return render_template('trial_cart.html', login_message="Login to do Checkout")

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('trial_cart.html', login_message="Login to do Checkout")
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('trial_cart.html', login_message="Login to do Checkout")
    
    return render_template('location.html', user_name = user.user_name)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Get form data
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        # Validation (optional)
        if not name or not email or not message:
            flash('Please fill in all fields', 'error')
            return redirect('/contact')

        # Send email to support (your email)
        support_msg = Message(subject=f"New Contact Us Form from {name}",
                              body=f"Message from {name} ({email}):\n\n{message}",
                              recipients=['soham.daddikar22@spit.ac.in'])
        mail.send(support_msg)

        # Send auto-reply to the user
        reply_msg = Message(subject="We received your message",
                            body=f"Hi {name},\n\nThank you for reaching out! We have received your message and will get back to you shortly.\n\nBest regards,\nThe Recipe Team",
                            recipients=[email])
        mail.send(reply_msg)

        # Notify user on the webpage
        flash('Your message has been sent! We will get back to you soon.', 'success')
        return redirect('/contact')

    return render_template('home.html')

@app.route('/search', methods = ['GET', 'POST'])
def search():
    items = Item.query.all()
    
    menu_data = [
        {
            "id": item.item_id,
            "name": item.item_name,
            "price": item.item_price,
            "image": item.item_image if item.item_image else None
        }
        for item in items
    ]
    
    token = request.cookies.get('access_token')
    if not token:
        return render_template('searchPage.html', menu_data = menu_data)

    # Verify and decode the token
    email = verify_access_token(token)
    if not email:
        return render_template('searchPage.html', menu_data = menu_data)
    
    # Fetch user details from the database
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return render_template('searchPage.html', menu_data = menu_data)
    
    return render_template('searchPage.html', menu_data = menu_data, user_name = user.user_name)

@app.route('/update_cart_recipe', methods = ['GET', 'POST', 'PUT', 'DELETE'])
def update_cart():
    data = request.get_json()
    ingredient_id = data['ingredient_id']
    ingredient_name = data['ingredient_name']
    quantity = data['quantity']

    # Retrieve the image from the Item table
    item = Item.query.filter_by(item_name=ingredient_name).first()
    if not item:
        return jsonify({'error': 'Item not found'}), 404

    # Find if the ingredient is already in the cart
    cart_entry = Cart.query.filter_by(cart_name=ingredient_name).first()

    if cart_entry:
        # Update quantity if the item is already in the cart
        if quantity > 0:
            cart_entry.cart_quantity = quantity
        else:
            # If quantity is 0, remove the item from the cart
            db.session.delete(cart_entry)
    else:
        # Insert new entry if it doesn't exist and quantity > 0
        if quantity > 0:
            new_cart_entry = Cart(
                cart_name=ingredient_name,
                cart_category=item.item_category,
                cart_quantity=quantity,
                cart_image=item.item_image,
                cart_price = item.item_price
            )
            db.session.add(new_cart_entry)

    # Commit changes to the database
    db.session.commit()
    return jsonify({'message': 'Cart updated successfully'})

@app.route('/ingredient_to_cart', methods=['GET', 'POST', 'PUT', 'DELETE'])
def add_to_cart():
    data = request.get_json()
    ingredients = data.get('ingredients', [])

    for ingredient_name in ingredients:
        # Retrieve item details for each ingredient
        non_veg_keywords = ['chicken', 'fish', 'mutton', 'shrimp', 'egg']
        is_non_veg = any(keyword.lower() in ingredient_name.lower() for keyword in non_veg_keywords)
        veg_status = 1 if is_non_veg else 0
        # Check if the ingredient is already in the cart
        cart_entry = Cart.query.filter_by(cart_name=ingredient_name).first()
        if cart_entry:
            # If exists, increase quantity by 1
            cart_entry.cart_quantity += 1
        else:
            # Add new entry to the cart
            new_cart_entry = Cart(
                cart_name=ingredient_name,
                cart_category=veg_status,
                cart_quantity=1,
                cart_price = random.randint(5, 20)
            )
            db.session.add(new_cart_entry)

    # Commit all changes to the database
    db.session.commit()
    return jsonify({'message': 'Ingredients added to cart successfully'})
    

@app.route('/item', methods = ['GET', 'POST', 'PUT', 'DELETE'])
def item():
    if request.method == 'POST' or request.method == 'PUT' or request.method == 'DELETE':
        item_name = request.form['item_name']
        item_category = request.form['item_category']
        item_quantity = request.form['item_quantity']
        item_image = request.form['item_image']
        item_ingredients = request.form['item_ingredients']
        item_steps = request.form['item_steps']
        item_nutrients = request.form['item_nutrients']
        
        item_quantity = int(item_quantity)
        item_category = int(item_category)
        
        if request.method == 'POST':
            new_item = Item(item_name = item_name, item_category = item_category, item_quantity = item_quantity, item_image = item_image, item_ingredients = item_ingredients, item_steps = item_steps, item_nutrients = item_nutrients)
            
            db.session.add(new_item)
            db.session.commit()
            
            return "Item Added"
        
        if request.method == 'PUT':
            item = Item.query.filter_by(item_name = item_name).first()
            
            item.item_name = item_name
            item.item_category = item_category
            item.item_quantity = item_quantity
            item.item_image = item_image
            item.item_ingredients = item_ingredients
            item.item_steps = item_steps
            item.item_nutrients = item_nutrients
            
            db.session.commit()
            
            return "Item Updated"
        
        if request.method == 'DELETE':
            item = Item.query.filter_by(item_name = item_name).first()
            
            db.session.delete(item)
            db.session.commit()
            
            return "Item Deleted"
            
    return "Item Retrieved"
        
        

@app.route('/logout')
def logout():
    response = redirect(url_for('home'))  # Redirect to home page
    response.set_cookie('access_token', '', expires=0)  # Expire the access token cookie
    session.clear()
    return response

@app.route('/profile')
def profile():
    token = request.cookies.get('access_token')
    if not token:
        return redirect(url_for('login'))
    
    email = verify_access_token(token)
    if not email:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return redirect(url_for('login'))
    
    # Determine profile image URL
    if user.profile_image:
        profile_image_url = url_for('uploaded_file', filename=user.profile_image)
    else:
        # Default profile image
        profile_image_url = url_for('static', filename='default_profile.png')
    
    return render_template('profile.html',
                           user_name=user.user_name,
                           user_mail=user.user_mail,
                           user_city=user.user_city,
                           user_state=user.user_state,
                           user_country=user.user_country,
                           user_extra_address=user.user_extra_address,
                           profile_image_url=profile_image_url)

@app.route('/upload-profile-image', methods=['POST'])
def upload_profile_image():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    email = verify_access_token(token)
    if not email:
        return jsonify({'status': 'error', 'message': 'Invalid token'}), 401

    user = User.query.filter_by(user_mail=email).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    if 'profile_image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    
    file = request.files['profile_image']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        if user.profile_image:
            # Delete the old profile image if exists
            old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_image)
            if os.path.exists(old_image_path):
                os.remove(old_image_path)
        
        # Rename the file to include user_id to prevent name conflicts
        file_ext = os.path.splitext(filename)[1]
        new_filename = f"user_{user.user_id}{file_ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        file.save(file_path)
        
        # Update user profile_image in the database
        user.profile_image = new_filename
        db.session.commit()
        
        profile_image_url = url_for('uploaded_file', filename=new_filename)
        
        return jsonify({'status': 'success', 'profile_image_url': profile_image_url}), 200
    else:
        return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400

def allowed_file(filename):
    allowed_extensions = {'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/static/profile_pics/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
if __name__ == "__main__":
    app.run()
