from flask import Flask, render_template, request
import os
from PIL import Image
import torch
import io
from transformers import AutoFeatureExtractor, AutoModelForImageClassification
from torchvision import transforms
import joblib
import requests

app = Flask(__name__)

# --- Load Models ---
# Crop Recommendation Model
crop_model = joblib.load("crop_model.pkl")
crop_label_encoder = joblib.load("crop_label_encoder (1).pkl")

# Disease Detection Model (HuggingFace)
DISEASE_MODEL_NAME = "wambugu71/crop_leaf_diseases_vit"
disease_extractor = AutoFeatureExtractor.from_pretrained(DISEASE_MODEL_NAME)
disease_model = AutoModelForImageClassification.from_pretrained(DISEASE_MODEL_NAME)

# --- Helper Functions ---
def get_weather_emoji(condition):
    condition = condition.lower()
    if "sun" in condition: return "☀️"
    elif "rain" in condition: return "🌧️"
    elif "cloud" in condition: return "☁️"
    elif "snow" in condition: return "❄️"
    elif "storm" in condition: return "🌩️"
    else: return "🌤️"

def geocode_city(city):
    # Use Nominatim to get lat/lon from city name
    try:
        url = f"https://nominatim.openstreetmap.org/search"
        params = {"q": city, "format": "json", "limit": 1}
        headers = {"User-Agent": "SmartKrishiAssistant/1.0"}
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if data:
            lat = data[0]["lat"]
            lon = data[0]["lon"]
            display_name = data[0]["display_name"]
            return lat, lon, display_name
        else:
            return None, None, None
    except Exception:
        return None, None, None

def fetch_forecast(city):
    # Use weatherapi.com for accurate weather, fallback to Open-Meteo for small villages/pincodes
    API_KEY = os.environ.get('WEATHER_API_KEY', '0af6240444ce4b338ee84240251007')
    try:
        url = f"http://api.weatherapi.com/v1/current.json"
        params = {"key": API_KEY, "q": city, "aqi": "no"}
        response = requests.get(url, params=params)
        print(f"[DEBUG] Weather API URL: {response.url}")
        print(f"[DEBUG] Weather API status: {response.status_code}")
        print(f"[DEBUG] Weather API response: {response.text}")
        data = response.json()
        if 'error' in data or 'current' not in data:
            # Fallback: Use Nominatim to get lat/lon, then Open-Meteo
            print(f"[DEBUG] WeatherAPI failed, using Nominatim + Open-Meteo fallback for: {city}")
            lat, lon, display_name = geocode_city(city)
            if not lat or not lon:
                return {'forecast': f"⚠️ Location not found. Try a different city or pincode.", 'condition': None, 'emoji': '', 'temp': '', 'humidity': '', 'location': ''}
            try:
                openmeteo_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": True,
                    "hourly": "relative_humidity_2m"
                }
                om_response = requests.get(openmeteo_url, params=params)
                print(f"[DEBUG] Open-Meteo URL: {om_response.url}")
                print(f"[DEBUG] Open-Meteo response: {om_response.text}")
                om_data = om_response.json()
                if "current_weather" in om_data:
                    weather = om_data["current_weather"]
                    temp = weather["temperature"]
                    code = weather["weathercode"]
                    # Map code to condition
                    code_map = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Depositing rime fog", 51: "Drizzle", 61: "Rain", 71: "Snow", 80: "Rain showers", 95: "Thunderstorm"}
                    condition = code_map.get(code, "Unknown")
                    emoji = get_weather_emoji(condition)
                    # Try to get humidity from hourly data
                    humidity = ''
                    if "hourly" in om_data and "relative_humidity_2m" in om_data["hourly"]:
                        humidity = om_data["hourly"]["relative_humidity_2m"][0]
                    return {
                        'forecast': f"{emoji} {condition}, {temp}°C, Humidity: {humidity}%",
                        'condition': condition,
                        'emoji': emoji,
                        'temp': temp,
                        'humidity': humidity,
                        'location': display_name
                    }
                else:
                    return {'forecast': "⚠️ Weather data unavailable.", 'condition': None, 'emoji': '', 'temp': '', 'humidity': '', 'location': display_name}
            except Exception as e:
                print(f"[ERROR] Exception in Open-Meteo fallback: {e}")
                return {'forecast': f"⚠️ Unable to fetch forecast: {e}", 'condition': None, 'emoji': '', 'temp': '', 'humidity': '', 'location': display_name}
        else:
            condition = data['current']['condition']['text']
            temp = data['current']['temp_c']
            humidity = data['current'].get('humidity', '')
            emoji = get_weather_emoji(condition)
            return {
                'forecast': f"{emoji} {condition}, {temp}°C, Humidity: {humidity}%",
                'condition': condition,
                'emoji': emoji,
                'temp': temp,
                'humidity': humidity,
                'location': data['location']['name']
            }
    except Exception as e:
        print(f"[ERROR] Exception in fetch_forecast: {e}")
        return {'forecast': f"⚠️ Unable to fetch forecast: {e}", 'condition': None, 'emoji': '', 'temp': '', 'humidity': '', 'location': ''}

# --- Routes ---
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/crop', methods=['GET', 'POST'])
def crop():
    result = None
    if request.method == 'POST':
        try:
            data = [float(request.form.get(key)) for key in ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
            prediction = crop_model.predict([data])[0]
            result = crop_label_encoder.inverse_transform([prediction])[0]
        except Exception:
            result = "Something went wrong. Please check your input."
    return render_template('crop.html', result=result)

@app.route('/weather', methods=['GET', 'POST'])
def weather():
    forecast_data = None
    if request.method == 'POST':
        location = request.form.get('location')
        forecast_data = fetch_forecast(location)
    return render_template('weather.html', forecast_data=forecast_data)

@app.route('/disease', methods=['GET', 'POST'])
def disease():
    result = None
    if request.method == 'POST':
        try:
            image_file = request.files['leaf']
            if image_file:
                img_bytes = image_file.read()
                image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                # Hugging Face preprocessing
                inputs = disease_extractor(images=image, return_tensors="pt")
                with torch.no_grad():
                    outputs = disease_model(**inputs)
                    logits = outputs.logits
                    predicted_class = logits.argmax(-1).item()
                    result = disease_model.config.id2label[predicted_class]
            else:
                result = "No image uploaded."
        except Exception as e:
            result = f"⚠️ Error: {e}"
    return render_template('disease.html', result=result)

if __name__ == '__main__':
    app.run(debug=True,port=5050)
