from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import markdown
import random
from youtube_search import YoutubeSearch
from googleapiclient.discovery import build

app = Flask(__name__)
""" app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:Ssd11012004+-=@localhost:3306/food_delivery" """
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///food_delivery.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
GEMINI_API_KEY = "AIzaSyAK2WsGSgro8ySMQsZWg4Q55ZT_rOAblOg"
YOUTUBE_API_KEY = "AIzaSyCFgSOZz8R-bog8Thj_midN4wxxPPWA0Ys"
WEATHER_API_KEY = "997060352864d28d4fdb7259b8b0eb81"
db = SQLAlchemy(app)

# Database declaration
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
    item_category = db.Column(db.Boolean, nullable = False)
    item_quantity = db.Column(db.Integer, nullable = False)
    item_image = db.Column(db.String(800), nullable = True)
    item_ingredients = db.Column(db.String(4000), nullable = True)
    item_steps = db.Column(db.String(4000), nullable = True)
    item_nutrients = db.Column(db.String(4000), nullable = True)
    item_timing = db.Column(db.String(900), nullable = True)
    item_youtube = db.Column(db.String(800), nullable = True)
    item_price = db.Column(db.Integer, nullable = False)
    
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


@app.route('/') # Website For Recipe Name Input
def index():
    return render_template('scrape_form.html')

@app.route('/loading')# loading page
def loading():
    recipe_name = request.args.get('recipe_name')
    # Redirect to the recipe results page after showing the loading screen
    return redirect(url_for('get_recipe', recipe_name=recipe_name))

#Recipe display page
@app.route('/recipe', methods = ['GET', 'POST'])
def get_recipe():
    recipe_name = request.args.get('recipe_name')
    
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
        
        return render_template('scrape_test.html', recipe_data=recipe_data, recipe_name=existing_recipe.item_name, display_category=display_category, video_url = existing_recipe.item_youtube, food_suggestion = food_suggestion)
    
    
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

    return render_template('scrape_test.html', recipe_data = recipe_data, recipe_name = recipe_name, display_category = display_category, video_url = video_url, food_suggestion = food_suggestion)

if __name__ == '__main__':
    app.run(debug=True)
