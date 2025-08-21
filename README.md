# Smart-Krishi-Assistant

A Flask-based assistant with crop recommendation, weather insights, and plant disease detection.

## Prerequisites
- Python 3.9+ recommended
- pip

## Installation
1. Clone the repo and enter the project directory:
   ```bash
   git clone <your-repo-url>
   cd Smart Krishi Assistant
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration
Create a `.env` file (or set environment variables) with the following:
```env
# Weather API (required)
WEATHER_API_KEY=your-weatherapi-com-key

# Optional: PORT for server (Render sets this automatically)
# PORT=10000
```

Tip: For more accurate weather results, use the pincode of your area when searching.

## Run Locally
```bash
python app.py
```
Default local URL: `http://localhost:10000` (or the value of `PORT` if set).

On first run, the disease detection model will be downloaded automatically.

## Features
- Crop Recommendation
  - Input soil and climate parameters (N, P, K, temperature, humidity, pH, rainfall)
  - Returns the recommended crop

- Weather
  - Uses `weatherapi.com` (enter city/village/pincode)
  - Fallback geocoding via Nominatim + Open‑Meteo to improve small-village support
  - Displays condition, temperature, humidity, and dynamic background effects
  - Tip: Use your pincode for best results

- Plant Disease Detection
  - Upload a leaf image to detect potential diseases using a pretrained vision model

## Project Structure
```
Smart Krishi Assistant/
├─ app.py
├─ models.py
├─ email_config.py
├─ requirements.txt
├─ env_example.txt
├─ crop_model.pkl
├─ crop_label_encoder (1).pkl
├─ static/
│  └─ style.css
└─ templates/
   ├─ welcome.html
   ├─ home.html
   ├─ crop.html
   ├─ weather.html
   ├─ disease.html
   ├─ login.html
   ├─ register.html
   └─ verify_otp.html
```

## Deployment (Render)
1. Push the repository to GitHub/GitLab.
2. Create a new Web Service on Render:
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
3. Add environment variables:
   - `WEATHER_API_KEY`
4. Render will set `PORT` automatically; the app already reads it.

## Troubleshooting
- Weather shows unavailable or wrong location:
  - Ensure `WEATHER_API_KEY` is set and valid
  - Try using a pincode for higher accuracy
- Disease model download is slow or fails on first run:
  - Ensure stable internet
  - Retry after some time; the model is cached after initial download
- Port conflicts locally:
  - Set a custom `PORT`, e.g. `PORT=5000`, then `python app.py`

## Acknowledgements
- Weather data: `weatherapi.com`
- Geocoding: Nominatim (OpenStreetMap)
- Disease detection: Pretrained vision model (Hugging Face)

## Live Demo 
- You can check out the live app here : https://smart-krishi-assistant.onrender.com

<img width="1923" height="865" alt="image" src="https://github.com/user-attachments/assets/dd3be727-5cbb-4512-ba75-44461a67343e" />

<img width="1923" height="865" alt="image" src="https://github.com/user-attachments/assets/2eb02407-2026-472d-a1a9-aa977f432748" />

<img width="1923" height="865" alt="image" src="https://github.com/user-attachments/assets/d4072ee8-5b78-44ba-8f9f-b358d917458c" />

<img width="1923" height="865" alt="image" src="https://github.com/user-attachments/assets/14fa090f-848e-4b75-9578-3bc38e84fa0f" />

<img width="1923" height="865" alt="image" src="https://github.com/user-attachments/assets/d11d09e4-1b5b-4ec3-895b-70ed7cea7dee" />
