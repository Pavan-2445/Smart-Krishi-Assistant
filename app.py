from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
import os
from PIL import Image
import io
import joblib
import requests
import re
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import random
from typing import Optional
import mysql.connector
from mysql.connector import pooling
import smtplib
import threading
import time
from email.message import EmailMessage


app = Flask(__name__)

load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY")

def validate_brevo_key():
    key = (os.getenv("BREVO_API_KEY") or "").strip()
    if not key or key.startswith("<"):
        print("[WARN] BREVO API key is not set or appears to be a placeholder; Brevo email disabled.")
        return False
    try:
        resp = requests.get("https://api.brevo.com/v3/account", headers={"api-key": key}, timeout=6)
        if resp.status_code == 200:
            print("[INFO] Brevo API key validated successfully")
            return True
        else:
            print(f"[ERROR] Brevo API key validation failed (status={resp.status_code}) response={resp.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception during Brevo key validation: {e}")
        return False

validate_brevo_key()


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "port": os.getenv("MYSQL_PORT"),
    "ssl_disabled": True if os.getenv("MYSQL_SSL_DISABLED", "0") == "1" else False,
}

SUPPORTED_LANGS = {
    "en": {"label": "English"},
    "hi": {"label": "हिन्दी"},
    "te": {"label": "తెలుగు"},
}

STRINGS = {
    "en": {
        "app_name": "Smart Krishi Assistant",
        "choose_language": "Choose your language",
        "choose_language_subtitle": "You can change it anytime from the top right.",
        "continue": "Continue",
        "login_title": "Welcome back",
        "login_subtitle": "Login to continue",
        "register_title": "Create your account",
        "register_subtitle": "Join Smart Krishi Assistant in seconds",
        "email": "Email",
        "password": "Password",
        "name": "Full name",
        "age": "Age",
        "occupation": "Occupation",
        "login": "Login",
        "register": "Register",
        "no_account": "Don't have an account?",
        "have_account": "Already have an account?",
        "logout": "Logout",
        "get_started": "Get Started",
        "welcome_title": "Welcome to Smart Krishi Assistant",
        "home_heading": "Grow with Smart Krishi",
        "home_crop_title": "Crop Recommendation",
        "home_crop_sub": "Find the best crop for your soil and climate.",
        "home_weather_title": "Weather",
        "home_weather_sub": "See gentle, accurate weather for your farm.",
        "home_disease_title": "Disease Detection",
        "home_disease_sub": "Protect your plants with early disease alerts.",
        "crop_page_title": "Crop Recommendation",
        "crop_field_n": "Nitrogen (N)",
        "crop_field_p": "Phosphorus (P)",
        "crop_field_k": "Potassium (K)",
        "crop_field_temp": "Temperature (°C)",
        "crop_field_hum": "Humidity (%)",
        "crop_field_ph": "pH",
        "crop_field_rain": "Rainfall (mm)",
        "crop_recommend_button": "Recommend Crop",
        "weather_page_title": "Weather",
        "weather_placeholder": "Enter city, village, or pincode",
        "weather_tip": "Tip: For more accurate results, use your area pincode.",
        "otp_title": "Verify your account",
        "otp_subtitle": "We’ve sent a 6-digit code to your email (demo: shown below).",
        "otp_label": "One-Time Password (OTP)",
        "verify": "Verify",
        "forgot_title": "Forgot your password?",
        "forgot_subtitle": "We’ll send you a small code to reset it.",
        "forgot_email_label": "Registered email",
        "forgot_send": "Send OTP",
        "reset_title": "Set a new password",
        "reset_subtitle": "Enter the code and your new password.",
        "reset_password_label": "New password",
        "reset_button": "Reset password",
        "pincode": "Pincode",
        "forgot_password": "Forgot password?",
    },
    "hi": {
        "app_name": "स्मार्ट कृषि सहायक",
        "choose_language": "अपनी भाषा चुनें",
        "choose_language_subtitle": "आप इसे कभी भी ऊपर दाईं ओर से बदल सकते हैं।",
        "continue": "आगे बढ़ें",
        "login_title": "वापसी पर स्वागत है",
        "login_subtitle": "जारी रखने के लिए लॉगिन करें",
        "register_title": "अपना खाता बनाएँ",
        "register_subtitle": "कुछ ही सेकंड में जुड़ें",
        "email": "ईमेल",
        "password": "पासवर्ड",
        "name": "पूरा नाम",
        "age": "आयु",
        "occupation": "पेशा",
        "login": "लॉगिन",
        "register": "रजिस्टर",
        "no_account": "खाता नहीं है?",
        "have_account": "पहले से खाता है?",
        "logout": "लॉगआउट",
        "get_started": "शुरू करें",
        "welcome_title": "स्मार्ट कृषि सहायक में आपका स्वागत है",
        "home_heading": "स्मार्ट कृषि के साथ बढ़ें",
        "home_crop_title": "फसल अनुशंसा",
        "home_crop_sub": "आपकी मिट्टी और मौसम के लिए सबसे अच्छी फसल चुनें।",
        "home_weather_title": "मौसम",
        "home_weather_sub": "आपके खेत के लिए प्यारा, सही मौसम विवरण।",
        "home_disease_title": "रोग पहचान",
        "home_disease_sub": "पौधों को सुरक्षित रखें, रोग जल्दी पहचानें।",
        "crop_page_title": "फसल अनुशंसा",
        "crop_field_n": "नाइट्रोजन (N)",
        "crop_field_p": "फॉस्फोरस (P)",
        "crop_field_k": "पोटैशियम (K)",
        "crop_field_temp": "तापमान (°C)",
        "crop_field_hum": "नमी (%)",
        "crop_field_ph": "pH",
        "crop_field_rain": "वर्षा (mm)",
        "crop_recommend_button": "फसल सुझाएँ",
        "weather_page_title": "मौसम",
        "weather_placeholder": "शहर, गाँव या पिनकोड दर्ज करें",
        "weather_tip": "सुझाव: ज्यादा सही परिणाम के लिए अपना पिनकोड डालें।",
        "otp_title": "अपना खाता सत्यापित करें",
        "otp_subtitle": "हमने 6-अंक का कोड भेजा है (डेमो: नीचे दिखाया जाएगा)।",
        "otp_label": "वन-टाइम पासवर्ड (OTP)",
        "verify": "सत्यापित करें",
        "forgot_title": "पासवर्ड भूल गए?",
        "forgot_subtitle": "रीसेट करने के लिए छोटा कोड भेजेंगे।",
        "forgot_email_label": "पंजीकृत ईमेल",
        "forgot_send": "OTP भेजें",
        "reset_title": "नया पासवर्ड सेट करें",
        "reset_subtitle": "कोड और नया पासवर्ड दर्ज करें।",
        "reset_password_label": "नया पासवर्ड",
        "reset_button": "पासवर्ड रीसेट करें",
        "pincode": "पिनकोड",
        "forgot_password": "पासवर्ड भूल गए?",
    },
    "te": {
        "app_name": "స్మార్ట్ కృషి సహాయకుడు",
        "choose_language": "మీ భాషను ఎంచుకోండి",
        "choose_language_subtitle": "మీరు ఎప్పుడైనా పై కుడి మూలలో మార్చుకోవచ్చు.",
        "continue": "కొనసాగించండి",
        "login_title": "తిరిగి స్వాగతం",
        "login_subtitle": "కొనసాగించడానికి లాగిన్ అవ్వండి",
        "register_title": "మీ ఖాతాను సృష్టించండి",
        "register_subtitle": "కొన్ని క్షణాల్లో చేరండి",
        "email": "ఇమెయిల్",
        "password": "పాస్‌వర్డ్",
        "name": "పూర్తి పేరు",
        "age": "వయస్సు",
        "occupation": "వృత్తి",
        "login": "లాగిన్",
        "register": "రిజిస్టర్",
        "no_account": "ఖాతా లేదు?",
        "have_account": "ఇప్పటికే ఖాతా ఉందా?",
        "logout": "లాగ్ అవుట్",
        "get_started": "ప్రారంభించండి",
        "welcome_title": "స్మార్ట్ కృషి సహాయకుడికి స్వాగతం",
        "home_heading": "స్మార్ట్ కృషితో కలిసి ఎదగండి",
        "home_crop_title": "పంట సూచన",
        "home_crop_sub": "మీ నేల, వాతావరణానికి సరైన పంటను కనుగొనండి.",
        "home_weather_title": "వాతావరణం",
        "home_weather_sub": "మీ పొలానికి మృదువైన, ఖచ్చితమైన వాతావరణ సమాచారం.",
        "home_disease_title": "వ్యాధి గుర్తింపు",
        "home_disease_sub": "వ్యాధిని ముందే గుర్తించి మీ మొక్కలను కాపాడండి.",
        "crop_page_title": "పంట సూచన",
        "crop_field_n": "నైట్రోజన్ (N)",
        "crop_field_p": "ఫాస్పరస్ (P)",
        "crop_field_k": "పొటాషియం (K)",
        "crop_field_temp": "ఉష్ణోగ్రత (°C)",
        "crop_field_hum": "ఆర్ద్రత (%)",
        "crop_field_ph": "pH",
        "crop_field_rain": "వర్షపాతం (mm)",
        "crop_recommend_button": "పంటను సూచించు",
        "weather_page_title": "వాతావరణం",
        "weather_placeholder": "నగరం, గ్రామం లేదా పిన్‌కోడ్ నమోదు చేయండి",
        "weather_tip": "సూచన: మరింత ఖచ్చితత్వం కోసం మీ ప్రాంతం పిన్‌కోడ్ వాడండి.",
        "otp_title": "మీ ఖాతాను నిర్ధారించండి",
        "otp_subtitle": "మేము 6 అంకెల కోడ్ పంపాం (డెమోలో క్రింద చూపబడుతుంది).",
        "otp_label": "ఒకసారి వాడే పాస్‌వర్డ్ (OTP)",
        "verify": "నిర్ధారించు",
        "forgot_title": "పాస్‌వర్డ్ మర్చిపోయారా?",
        "forgot_subtitle": "రీసెట్‌ కోసం చిన్న కోడ్‌ను పంపుతాం.",
        "forgot_email_label": "నమోదైన ఇమెయిల్",
        "forgot_send": "OTP పంపు",
        "reset_title": "క్రొత్త పాస్‌వర్డ్ సెటప్ చేయండి",
        "reset_subtitle": "కోడ్ మరియు క్రొత్త పాస్‌వర్డ్ నమోదు చేయండి.",
        "reset_password_label": "క్రొత్త పాస్‌వర్డ్",
        "reset_button": "పాస్‌వర్డ్ రీసెట్ చేయండి",
        "pincode": "పిన్‌కోడ్",
        "forgot_password": "పాస్‌వర్డ్ మర్చిపోయారా?",
    },
}


def t(key: str) -> str:
    lang = session.get("lang", "en")
    if lang not in STRINGS:
        lang = "en"
    return STRINGS[lang].get(key, STRINGS["en"].get(key, key))

DB_POOL = None
def init_db_pool():
    global DB_POOL
    try:
        pool_size = int(os.getenv("MYSQL_POOL_SIZE", "5"))
    except Exception:
        pool_size = 5
    pool_size = max(3, min(5, pool_size))
    pool_name = os.getenv("MYSQL_POOL_NAME", "smartkrishi_pool")
    try:
        DB_POOL = pooling.MySQLConnectionPool(pool_name=pool_name, pool_size=pool_size, **DB_CONFIG)
        print(f"[INFO] Initialized MySQL connection pool '{pool_name}' with size {pool_size}")
    except Exception as e:
        print(f"[WARN] Failed to initialize DB pool: {e}")
        DB_POOL = None

init_db_pool()

def get_db():
    if DB_POOL:
        try:
            return DB_POOL.get_connection()
        except Exception as e:
            print(f"[WARN] DB_POOL.get_connection failed ({e}); falling back to direct connection")
    return mysql.connector.connect(**DB_CONFIG)

_auth_schema_ensured = False
def ensure_auth_schema():
    global _auth_schema_ensured
    if _auth_schema_ensured:
        return
    try:
        db = get_db()
        cur = db.cursor()
        for col, defn in [
            ("pincode", "VARCHAR(20) DEFAULT NULL"),
            ("location_data", "TEXT DEFAULT NULL"),
            ("phone", "VARCHAR(30) DEFAULT NULL"),
            ("is_farmer", "TINYINT(1) DEFAULT 0"),
            ("farmer_pin_hash", "VARCHAR(200) DEFAULT NULL")
        ]:
            try:
                cur.execute(f"ALTER TABLE user_details ADD COLUMN {col} {defn}")
                db.commit()
                print(f"[INFO] ensure_auth_schema: added column {col}")
            except mysql.connector.Error as e:
                if e.errno == 1060:
                    print(f"[DEBUG] ensure_auth_schema: column {col} already exists")
                else:
                    print(f"[WARN] ensure_auth_schema add column {col} failed: {e}")
        try:
            cur.execute("ALTER TABLE user_details MODIFY COLUMN otp_purpose VARCHAR(50) DEFAULT NULL")
            db.commit()
            print("[INFO] ensure_auth_schema: modified otp_purpose size")
        except mysql.connector.Error as e:
            print(f"[WARN] could not modify otp_purpose: {e}")

        try:
            cur.execute("ALTER TABLE user_details MODIFY COLUMN password_hash VARCHAR(200) DEFAULT NULL")
            db.commit()
            print("[INFO] ensure_auth_schema: made password_hash nullable")
        except mysql.connector.Error as e:
            print(f"[WARN] could not modify password_hash nullability: {e}")

        try:
            cur.execute("ALTER TABLE user_details ADD UNIQUE INDEX uq_user_phone (phone)")
            db.commit()
            print("[INFO] ensure_auth_schema: added unique index on phone")
        except mysql.connector.Error as e:
            if e.errno in (1061, 1060):
                print("[DEBUG] ensure_auth_schema: unique index on phone already exists")
            else:
                print(f"[WARN] could not add unique index on phone: {e}")

        cur.close()
        db.close()
    except Exception as e:
        print(f"[ERROR] ensure_auth_schema top-level failure: {e}")
    _auth_schema_ensured = True


def get_user_by_email(email: str):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user_details WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    db.close()
    return user


def get_user_by_identifier(identifier: str):
    """Look up a user by email or phone (identifier can be email or phone)."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    db = get_db()
    cur = db.cursor(dictionary=True)
    # Try phone first if looks numeric
    if identifier.isdigit():
        cur.execute("SELECT * FROM user_details WHERE phone=%s", (identifier,))
        user = cur.fetchone()
        if user:
            cur.close()
            db.close()
            return user
    cur.execute("SELECT * FROM user_details WHERE email=%s", (identifier.lower(),))
    user = cur.fetchone()
    cur.close()
    db.close()
    return user


def create_user(name: str, email: str = None, password: str = None, age: str = "", occupation: str = "", pincode: str = "", location_data: str = "", phone: str = None, is_farmer: int = 0, farmer_pin: str = None):
    """Create a user. For non-farmers, `email` should be provided. For farmers provide `phone` and `farmer_pin`.
    If `password` is None for non-farmers, they will be created unverified and asked to verify via OTP before setting a password."""
    db = get_db()
    cur = db.cursor()

    password_hash = generate_password_hash(password) if password else ""
    farmer_pin_hash = generate_password_hash(farmer_pin) if farmer_pin else None
    if not email:
        if phone:
            cur.execute("SELECT id FROM user_details WHERE phone=%s", (phone,))
            if cur.fetchone():
                cur.close()
                db.close()
                raise ValueError("Phone number already registered")
            email_val = f"phone_{phone}_{int(datetime.now().timestamp())}@no-email.local"
        else:
            email_val = f"user_{int(datetime.now().timestamp())}@no-email.local"
    else:
        email_val = email

    try:
        cur.execute(
            """
            INSERT INTO user_details (name, email, age, occupation, password_hash, pincode, location_data, phone, is_farmer, farmer_pin_hash, verified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                email_val,
                age or None,
                occupation or "",
                password_hash,
                pincode or None,
                location_data or "",
                phone or None,
                1 if is_farmer else 0,
                farmer_pin_hash,
                1 if is_farmer else 0,
            ),
        )
        db.commit()
    except mysql.connector.Error as e:
        print(f"[ERROR] create_user insert failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        try:
            cur.execute(
                """
                INSERT INTO user_details (name, email, age, occupation, password_hash, pincode, location_data, phone, is_farmer, farmer_pin_hash, verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    email_val,
                    age or None,
                    occupation or "",
                    "",
                    pincode or None,
                    location_data or "",
                    phone or None,
                    1 if is_farmer else 0,
                    farmer_pin_hash,
                    1 if is_farmer else 0,
                ),
            )
            db.commit()
            print("[INFO] create_user: insert retry succeeded with empty password_hash")
        except Exception as e2:
            print(f"[ERROR] create_user retry failed: {e2}")
            cur.close()
            db.close()
            raise
    finally:
        cur.close()
        db.close()


def _generate_otp() -> str:
    return str(random.randint(100000, 999999))


def set_otp(email: str, purpose: str) -> Optional[str]:
    otp = _generate_otp()
    exp = datetime.now(timezone.utc) + timedelta(minutes=10)
    db = None
    cur = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            UPDATE user_details
            SET otp=%s, otp_purpose=%s, otp_expires_at=%s
            WHERE email=%s
            """,
            (otp, purpose, exp, email),
        )
        db.commit()
        cur.close()
        db.close()
        return otp
    except mysql.connector.Error as e:
        print(f"[ERROR] Failed to set OTP for {email}: {e}")
        try:
            if cur:
                cur.close()
            if db:
                db.close()
        except Exception:
            pass
        return None


def verify_otp_code(email: str, otp: str, purpose: str) -> bool:
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        """
        SELECT otp, otp_expires_at, otp_purpose FROM user_details
        WHERE email=%s AND otp=%s AND otp_purpose=%s
        """,
        (email, otp, purpose),
    )
    user = cur.fetchone()
    if not user:
        cur.close()
        db.close()
        print(f"[INFO] verify_otp: no matching OTP row for email={email} purpose={purpose}")
        return False
    exp = user.get("otp_expires_at")
    if not exp:
        cur.close()
        db.close()
        print(f"[INFO] verify_otp: missing expiry for email={email}")
        return False
    try:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
    except Exception:
        cur.close()
        db.close()
        print(f"[WARN] verify_otp: unexpected expiry format for {email}: {exp}")
        return False
    now = datetime.now(timezone.utc)
    if exp < now:
        cur.close()
        db.close()
        print(f"[INFO] verify_otp: expired OTP for email={email} (exp={exp.isoformat()}, now={now.isoformat()})")
        return False
    cur.execute(
        """
        UPDATE user_details
        SET otp=NULL, otp_purpose=NULL, otp_expires_at=NULL
        WHERE email=%s
        """,
        (email,),
    )
    db.commit()
    cur.close()
    db.close()
    return True


def mark_verified(email: str):
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE user_details SET verified=1 WHERE email=%s", (email,))
    db.commit()
    cur.close()
    db.close()


def update_password(email: str, password: str):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        UPDATE user_details SET password_hash=%s WHERE email=%s
        """,
        (generate_password_hash(password), email),
    )
    db.commit()
    cur.close()
    db.close()


def send_otp_email(to_email: str, otp: str, purpose: str) -> bool:
    subject_map = {
        "verify": "Your Smart Krishi verification code",
        "reset": "Your Smart Krishi password reset code",
    }
    subject = subject_map.get(purpose, "Your Smart Krishi OTP")

    text_body = (
        f"Namaste,\n\n"
        f"Your one-time password (OTP) for Smart Krishi ({purpose}) is: {otp}\n\n"
        f"This code will expire in 10 minutes.\n\n"
        f"If you did not request this, you can safely ignore this email.\n\n"
        f"– Smart Krishi Assistant"
    )

    html_body = (
        f"<html><body>"
        f"<p>Namaste,</p>"
        f"<p>Your one-time password (OTP) for <strong>Smart Krishi</strong> ({purpose}) is: <b>{otp}</b></p>"
        f"<p>This code will expire in 10 minutes.</p>"
        f"<p>If you did not request this, you can safely ignore this email.</p>"
        f"<p>– Smart Krishi Assistant</p>"
        f"</body></html>"
    )

    brevo_key = (os.getenv("BREVO_API_KEY") or "").strip()
    if brevo_key and not brevo_key.startswith("<"):
        brevo_url = os.getenv("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email")
        from_email = os.getenv("BREVO_FROM_EMAIL", os.getenv("SMTP_FROM", "no-reply@example.com"))
        sender_name = os.getenv("BREVO_SENDER_NAME", "Smart Krishi Assistant")
        payload = {
            "sender": {"email": from_email, "name": sender_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body
        }
        headers = {"api-key": brevo_key, "Content-Type": "application/json"}
        try:
            resp = requests.post(brevo_url, json=payload, headers=headers, timeout=10)
            if 200 <= resp.status_code < 300:
                print(f"[INFO] Sent OTP via Brevo to {to_email} for {purpose} (status={resp.status_code})")
                return True
            else:
                print(f"[ERROR] Brevo send failed (status={resp.status_code}) response={resp.text}")
        except Exception as e:
            print(f"[ERROR] Exception when sending via Brevo to {to_email}: {e}")
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM", username or "no-reply@example.com")

    if host and username and password:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        try:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)
            print(f"[INFO] Sent OTP email to {to_email} for {purpose} via SMTP")
            return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"[ERROR] SMTP auth failed for {to_email}: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to send OTP email to {to_email} via SMTP: {e}")
            return False
    print(f"[WARN] No email provider configured. OTP for {to_email} ({purpose}): {otp}")
    return False


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, name, email FROM user_details WHERE id=%s", (uid,))
    user = cur.fetchone()
    cur.close()
    db.close()
    return user
    
@app.context_processor
def inject_globals():
    return {
        "t": t,
        "supported_langs": SUPPORTED_LANGS,
        "current_lang": session.get("lang", None),
        "current_user": get_current_user(),
    }

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.pop("user_id", None)
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def enforce_language_choice():
    if request.endpoint in {"static", "language", "set_language"}:
        return None
    if not request.endpoint or session.get("lang"):
        return None
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("language", next=next_url))

crop_model = None
crop_label_encoder = None
def get_crop_model():
    global crop_model, crop_label_encoder
    if crop_model is None or crop_label_encoder is None:
        import joblib
        print("[INFO] Loading crop model and label encoder (lazy)")
        crop_model = joblib.load("crop_model.pkl")
        crop_label_encoder = joblib.load("crop_label_encoder (1).pkl")
    return crop_model, crop_label_encoder

DISEASE_API_URL = os.getenv('DISEASE_API_URL')
def call_disease_api(image_bytes, filename=None, content_type=None, timeout=15, max_retries=1):
    if not DISEASE_API_URL:
        raise RuntimeError('DISEASE_API_URL not configured')

    files = {'file': (filename or 'leaf.jpg', image_bytes, content_type or 'application/octet-stream')}
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(DISEASE_API_URL, files=files, timeout=timeout)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as e:
                    raise RuntimeError(f"Invalid JSON from disease API: {e}")
            else:
                raise RuntimeError(f"Disease API returned status {resp.status_code}")
        except requests.exceptions.RequestException as e:
            last_exc = e
            time.sleep(0.5)
            continue
    raise last_exc or RuntimeError('Disease API request failed')

def get_weather_emoji(condition):
    condition = condition.lower()
    if "sun" in condition: return "☀️"
    elif "rain" in condition: return "🌧️"
    elif "cloud" in condition: return "☁️"
    elif "snow" in condition: return "❄️"
    elif "storm" in condition: return "🌩️"
    else: return "🌤️"

def geocode_city(city):
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


def geocode_by_pincode(pincode: str):
    pincode = (pincode or "").strip()
    if not pincode or not pincode.isdigit():
        return None
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"postalcode": pincode, "country": "India", "format": "json", "limit": 1}
        headers = {"User-Agent": "SmartKrishiAssistant/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            return data[0].get("display_name")
        params = {"q": f"{pincode}, India", "format": "json", "limit": 1}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            return data[0].get("display_name")
        return None
    except Exception as e:
        print(f"[WARN] geocode_by_pincode failed for {pincode}: {e}")
        return None

def fetch_forecast(city):
    API_KEY = os.environ.get('WEATHER_API_KEY')
    try:
        url = f"http://api.weatherapi.com/v1/current.json"
        params = {"key": API_KEY, "q": city, "aqi": "no"}
        response = requests.get(url, params=params)
        print(f"[DEBUG] Weather API URL: {response.url}")
        print(f"[DEBUG] Weather API status: {response.status_code}")
        print(f"[DEBUG] Weather API response: {response.text}")
        data = response.json()
        if 'error' in data or 'current' not in data:
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
                    code_map = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Depositing rime fog", 51: "Drizzle", 61: "Rain", 71: "Snow", 80: "Rain showers", 95: "Thunderstorm"}
                    condition = code_map.get(code, "Unknown")
                    emoji = get_weather_emoji(condition)
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
@app.route("/")
def index():
    if not session.get("lang"):
        return redirect(url_for("language"))
    user = get_current_user()
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))
    return redirect(url_for("home"))

@app.route("/language")
def language():
    next_url = request.args.get("next") or url_for("login")
    return render_template("language.html", next_url=next_url)

@app.route("/set-language/<lang_code>")
def set_language(lang_code):
    if lang_code not in SUPPORTED_LANGS:
        lang_code = "en"
    session["lang"] = lang_code
    next_url = request.args.get("next") or url_for("login")
    return redirect(next_url)

@app.route('/api/geocode-pincode')
def api_geocode_pincode():
    pincode = (request.args.get('pincode') or '').strip()
    if not pincode:
        return jsonify({'display_name': None})
    display = geocode_by_pincode(pincode)
    return jsonify({'display_name': display})

@app.route('/admin/db-columns')
def admin_db_columns():
    if os.getenv('ENABLE_ADMIN') != '1':
        return jsonify({'error': 'disabled'}), 403
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='user_details'", (DB_CONFIG['database'],))
        cols = cur.fetchall()
        cur.close()
        db.close()
        return jsonify({'columns': [{'name': c[0], 'type': c[1]} for c in cols]})
    except Exception as e:
        print(f"[ERROR] admin_db_columns failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/ensure-auth-schema', methods=['POST'])
def admin_ensure_schema():
    if os.getenv('ENABLE_ADMIN') != '1':
        return jsonify({'error': 'disabled'}), 403
    try:
        ensure_auth_schema()
        return jsonify({'result': 'ok'})
    except Exception as e:
        print(f"[ERROR] admin_ensure_schema failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/get-otp')
def admin_get_otp():
    if os.getenv('ENABLE_ADMIN') != '1' and os.getenv('DEMO_SHOW_OTP') != '1':
        return jsonify({'error': 'disabled'}), 403
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'missing email'}), 400
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT otp, otp_expires_at FROM user_details WHERE email=%s", (email,))
        row = cur.fetchone()
        cur.close()
        db.close()
        if not row:
            return jsonify({'error': 'not found'}), 404
        return jsonify({'otp': row.get('otp'), 'expires_at': str(row.get('otp_expires_at'))})
    except Exception as e:
        print(f"[ERROR] admin_get_otp failed: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/welcome")
def welcome():
    return render_template("welcome.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    ensure_auth_schema()
    if request.method == "POST":
        occupation = (request.form.get("occupation") or "").strip()
        if occupation == "Farmer":
            name = (request.form.get("farmer_name") or request.form.get("name") or "").strip()
            phone = (request.form.get("phone") or "").strip()
            pincode = (request.form.get("pincode") or "").strip()
            farmer_pin = (request.form.get("farmer_pin") or "").strip()
            location_data = (request.form.get("location") or "").strip()

            if not name or not phone or not pincode or not farmer_pin:
                flash("Please fill all required fields for Farmer.", "error")
                return render_template("register.html")

            if not phone.isdigit() or len(phone) < 6:
                flash("Please enter a valid phone number.", "error")
                return render_template("register.html")

            if not pincode or not pincode.isdigit() or len(pincode) != 6:
                flash("Please enter a valid 6-digit pincode.", "error")
                return render_template("register.html")

            if not farmer_pin.isdigit() or len(farmer_pin) != 6:
                flash("Farmer PIN must be a 6-digit number.", "error")
                return render_template("register.html")

            if get_user_by_identifier(phone):
                flash("Phone already registered. Please login or use another number.", "error")
                return redirect(url_for("login"))

            if not location_data:
                try:
                    location_data = geocode_by_pincode(pincode) or ""
                except Exception as e:
                    print(f"[WARN] geocode fallback failed: {e}")
                    location_data = ""

            try:
                create_user(name=name, email=None, password=None, age="", occupation=occupation, pincode=pincode, location_data=location_data, phone=phone, is_farmer=1, farmer_pin=farmer_pin)
                flash("Registration complete. Farmers can login with phone and your 6-digit PIN.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                print(f"[ERROR] Failed to create farmer user: {e}")
                flash("Unable to complete registration right now. Please try again later.", "error")
                return render_template("register.html")

        name = (request.form.get("name") or request.form.get("user-name") or request.form.get("farmer_name") or "").strip()
        email = (request.form.get("email") or request.form.get("user-email") or "").strip().lower()

        if not name or not email:
            print(f"[WARN] register: missing name or email in POST data. Keys: {list(request.form.keys())}")
            flash("Please provide name and email.", "error")
            return render_template("register.html")

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash("Please enter a valid email.", "error")
            return render_template("register.html")

        existing = get_user_by_email(email)
        if existing:
            if existing.get("verified"):
                flash("Email already registered. Please login.", "error")
                return redirect(url_for("login"))
            otp_code = set_otp(email, "verify")
            if not otp_code:
                flash("Unable to send verification code right now. Please try again later.", "error")
                return render_template("register.html")
            sent = send_otp_email(email, otp_code, "verify")
            if not sent and os.getenv('DEMO_SHOW_OTP') == '1':
                flash(f"Demo OTP: {otp_code}", "success")
            if not sent:
                flash("We could not deliver the verification email. The code is generated; if you have it, enter it below.", "error")
            else:
                flash("We have sent a new OTP to your email. Enter it below to verify.", "success")
            return redirect(url_for("verify_otp", email=email))

        location_data = ''
        try:
            create_user(name=name, email=email, password=None, age="", occupation=occupation, pincode=None, location_data=location_data)
        except Exception as e:
            print(f"[ERROR] Failed to create user: {e}")
            flash("Unable to complete registration right now. Please try again later.", "error")
            return render_template("register.html")

        otp_code = set_otp(email, "verify")
        if not otp_code:
            flash("Unable to send verification code right now. Please try again later.", "error")
            return render_template("register.html")
        sent = send_otp_email(email, otp_code, "verify")
        if not sent and os.getenv('DEMO_SHOW_OTP') == '1':
            flash(f"Demo OTP: {otp_code}", "success")
        if not sent:
            flash("We could not deliver the verification email. The code is generated; if you have it, enter it on the next screen.", "error")
        else:
            flash("We have sent a verification code to your email. Please verify and set your password.", "success")
        return redirect(url_for("verify_otp", email=email))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            identifier = (request.form.get("identifier") or "").strip()
            password = request.form.get("password") or ""
            pin = (request.form.get("pin") or "").strip()

            user = get_user_by_identifier(identifier)
            if not user:
                flash("Invalid credentials", "error")
                return render_template("login.html")

            if user.get("is_farmer"):
                if not identifier.isdigit():
                    flash("Please enter your phone number to login as Farmer.", "error")
                    return render_template("login.html")
                if not pin or not pin.isdigit() or len(pin) != 6:
                    flash("Please enter your 6-digit PIN.", "error")
                    return render_template("login.html")
                if not user.get("farmer_pin_hash") or not check_password_hash(user.get("farmer_pin_hash"), pin):
                    flash("Invalid credentials", "error")
                    return render_template("login.html")
                session["user_id"] = user["id"]
                flash("Logged in successfully.", "success")
                next_url = request.args.get("next") or url_for("home")
                return redirect(next_url)
            if not user.get("password_hash") or not check_password_hash(user.get("password_hash"), password):
                flash("Invalid credentials", "error")
                return render_template("login.html")

            if not user.get("verified"):
                otp_code = set_otp(user["email"], "verify")
                if not otp_code:
                    flash("Unable to send verification code right now. Please try again later.", "error")
                    return render_template("login.html")
                send_otp_email(user["email"], otp_code, "verify")
                flash("Verify your account first. We've sent a code to your email.", "error")
                return redirect(url_for("verify_otp", email=user["email"]))

            otp_code = set_otp(user["email"], "login")
            if not otp_code:
                flash("Unable to send login code right now. Please try again later.", "error")
                return render_template("login.html")
            sent = send_otp_email(user["email"], otp_code, "login")
            if not sent and os.getenv('DEMO_SHOW_OTP') == '1':
                flash(f"Demo login OTP: {otp_code}", "success")
            if not sent:
                flash("We could not deliver the login code by email. The code has been generated; if you have it, enter it below.", "error")
            session["otp_purpose"] = "login"
            flash("We've sent a login code to your email. Enter it below.", "success")
            next_url = request.args.get("next") or url_for("home")
            return redirect(url_for("verify_otp", email=user["email"], purpose="login", next=next_url))
        except Exception as e:
            print(f"[ERROR] Exception during login: {e}")
            flash("An internal error occurred. Please try again.", "error")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = (request.args.get("email") or request.form.get("email") or "").strip().lower()
    purpose = request.args.get("purpose") or request.form.get("purpose") or session.get("otp_purpose") or "verify"
    if request.method == "POST":
        otp = (request.form.get("otp") or "").strip()
        post_purpose = request.form.get("purpose") or purpose
        if not email or not otp:
            flash("Please provide both email and OTP.", "error")
            return render_template("verify_otp.html", email=email, purpose=post_purpose)
        if verify_otp_code(email, otp, post_purpose):
            if post_purpose == "login":
                session.pop("otp_purpose", None)
                user = get_user_by_email(email)
                if user:
                    session["user_id"] = user["id"]
                    flash("Logged in successfully.", "success")
                    next_url = request.form.get("next") or request.args.get("next") or url_for("home")
                    return redirect(next_url)
            else:
                mark_verified(email)
                user = get_user_by_email(email)
                if user and not user.get("password_hash"):
                    session["set_password_email"] = email
                    flash("Verified. Please set your password.", "success")
                    return redirect(url_for("reset_password", email=email))
                flash("Account verified", "success")
                return redirect(url_for("login"))
        try:
            db = get_db()
            cur = db.cursor(dictionary=True)
            cur.execute("SELECT otp, otp_purpose, otp_expires_at FROM user_details WHERE email=%s", (email,))
            row = cur.fetchone()
            cur.close()
            db.close()
            if row:
                print(f"[INFO] verify_otp failed for {email}: submitted_otp={otp}, stored_otp={row.get('otp')}, stored_purpose={row.get('otp_purpose')}, expires_at={row.get('otp_expires_at')}")
                if os.getenv('DEMO_SHOW_OTP') == '1' and row.get('otp'):
                    flash(f"Demo OTP: {row.get('otp')}", "success")
            else:
                print(f"[INFO] verify_otp: no DB row found for {email}")
        except Exception as e:
            print(f"[ERROR] verify_otp diagnostic query failed: {e}")
        flash("Invalid OTP or expired. Please request a new code.", "error")
    return render_template("verify_otp.html", email=email, purpose=purpose)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if get_user_by_email(email):
            otp_code = set_otp(email, "reset")
            if otp_code:
                sent = send_otp_email(email, otp_code, "reset")
                if not sent and os.getenv('DEMO_SHOW_OTP') == '1':
                    flash(f"Demo reset OTP: {otp_code}", "success")
            else:
                print(f"[WARN] Unable to set reset OTP for {email}")
            flash("If that email exists, we have sent a reset code.", "success")
        else:
            flash("If that email exists, we have sent a reset code.", "success")
        return redirect(url_for("reset_password", email=email))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = (request.args.get("email") or request.form.get("email") or "").strip().lower()
    if request.method == "POST":
        if session.get("set_password_email") == email and request.form.get("password"):
            new_password = request.form.get("password") or ""
            if len(new_password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template("reset_password.html", email=email)
            if not re.search(r"[A-Za-z]", new_password) or not re.search(r"\d", new_password) or not re.search(r"[^A-Za-z0-9]", new_password):
                flash("Password must contain letters, digits, and special characters.", "error")
                return render_template("reset_password.html", email=email)
            update_password(email, new_password)
            session.pop("set_password_email", None)
            flash("Password set successfully. You can now login.", "success")
            return redirect(url_for("login"))

        otp = (request.form.get("otp") or "").strip()
        provided_password = request.form.get("password") or ""
        if otp:
            if verify_otp_code(email, otp, "reset"):
                session["set_password_email"] = email
                flash("OTP verified. Please enter your new password.", "success")
                return redirect(url_for("reset_password", email=email))
            else:
                flash("Invalid OTP or expired.", "error")
                return render_template("reset_password.html", email=email)

        flash("Please provide the OTP sent to your email.", "error")
        return render_template("reset_password.html", email=email)
    return render_template("reset_password.html", email=email)

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/crop', methods=['GET', 'POST'])
@login_required
def crop():
    result = None
    if request.method == 'POST':
        try:
            data = [float(request.form.get(key)) for key in ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']]
            crop_m, crop_le = get_crop_model()
            prediction = crop_m.predict([data])[0]
            result = crop_le.inverse_transform([prediction])[0]
        except Exception:
            result = "Something went wrong. Please check your input."
    return render_template('crop.html', result=result)

@app.route('/weather', methods=['GET', 'POST'])
@login_required
def weather():
    forecast_data = None
    if request.method == 'POST':
        location = request.form.get('location')
        forecast_data = fetch_forecast(location)
    return render_template('weather.html', forecast_data=forecast_data)

@app.route('/disease', methods=['GET', 'POST'])
@login_required
def disease():
    result = None
    if request.method == 'POST':
        image_file = request.files.get('leaf')
        if not image_file or image_file.filename == '':
            result = "No image uploaded."
            return render_template('disease.html', result=result)

        if not os.getenv('DISEASE_API_URL'):
            result = "⚠️ Disease detection is currently disabled (not configured). Contact admin."
            return render_template('disease.html', result=result)

        try:
            img_bytes = image_file.read()
            content_type = getattr(image_file, 'content_type', None)
            try:
                data = call_disease_api(img_bytes, filename=image_file.filename, content_type=content_type, timeout=15, max_retries=1)
                if isinstance(data, dict) and 'prediction' in data:
                    raw_pred = data.get('prediction') or "Unknown"
                    if isinstance(raw_pred, str):
                        result = raw_pred.replace("___", " - ").replace("_", " ")
                    else:
                        result = str(raw_pred)
                else:
                    result = "⚠️ Unexpected response from disease service."
            except requests.exceptions.Timeout:
                result = "⚠️ Disease service timed out. Please try again later."
            except requests.exceptions.RequestException as rexc:
                print(f"[ERROR] Disease API request failed: {rexc}")
                result = "⚠️ Disease service temporarily unavailable. Please try again later."
            except Exception as exc:
                print(f"[ERROR] Disease API error: {exc}")
                result = f"⚠️ Error: {exc}"
        except Exception as e:
            result = f"⚠️ Error processing uploaded image: {e}"
    return render_template('disease.html', result=result)


@app.route('/api/disease-health')
def disease_health():
    """Simple health-check for the external Disease API. Returns 200 JSON {status: 'up'} or 503 {status: 'down'}"""
    url = os.getenv('DISEASE_API_URL')
    if not url:
        return jsonify({"status": "down"}), 503
    try:
        health_url = url.replace('/predict', '/')
        r = requests.get(health_url, timeout=5)
        if r.status_code >= 200 and r.status_code < 500:
            return jsonify({"status": "up"})
        return jsonify({"status": "down"}), 503
    except Exception:
        return jsonify({"status": "down"}), 503


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
