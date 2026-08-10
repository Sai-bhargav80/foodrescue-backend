from fastapi import FastAPI, Depends, HTTPException, Body, UploadFile, File, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import random
import os
import smtplib
import uuid
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

import math

def calculate_distance(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 1.2
    try:
        R = 6371.0
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except:
        return 1.2

def calculate_priority_score(listing, lat=0.0, lng=0.0):
    return 100


import models, schemas, database
from database import engine, get_db
import jwt

# JWT Configurations
SECRET_KEY = "foodrescue-secret-key-12345"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# Load environment variables
load_dotenv()

# Create the database tables
models.Base.metadata.create_all(bind=engine)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections.values()):
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

app = FastAPI(title="FoodRescue API")

# Register admin dashboard router
from admin_dashboard import router as admin_dashboard_router
app.include_router(admin_dashboard_router)

# Register admin users router
from admin_users import router as admin_users_router
app.include_router(admin_users_router)

# Register behavior engine router
from behavior import router as behavior_router
app.include_router(behavior_router)

# Create uploads directories
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "food_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files to serve images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "FoodRescue FastAPI with MySQL is running!"}

def map_user_to_android(user, token="mock-jwt-token"):
    name = user.fullName
    if not name or name.strip() == "":
        if user.email:
            email_part = user.email.split("@")[0]
            name = email_part.replace(".", " ").replace("_", " ").title()
        else:
            name = "Rescuer"
            
    return {
        "id": str(user.id),
        "name": name,
        "email": user.email,
        "phone": user.phoneNumber or "",
        "avatarUrl": None,
        "rating": 5.0,
        "postsCount": user.donationsCount or 0,
        "claimsCount": user.rescuesCount or 0,
        "mealsCount": (user.rescuesCount or 0) + (user.donationsCount or 0),
        "location": "India",
        "token": token,
        "role": user.role,  # Return user role
        "mpin": user.mpin,
        "securityAnswer": user.securityAnswer,
        "hasMpin": bool(user.mpin),
        "trustScore": user.trust_score,
        "lastKnownLocation": user.last_known_location
    }

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization header")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token or expired session")
    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def get_current_admin_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing authorization header")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token or expired session")
    role = payload.get("role")
    if role not in ["ADMIN", "MODERATOR"]:
        raise HTTPException(status_code=403, detail="Admin or Moderator clearance required")
    user_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/logout")
def logout():
    return {"success": True, "message": "Logged out successfully"}

@app.post("/refresh")
def refresh():
    return {"token": "mock-jwt-token", "refreshToken": "mock-refresh-token"}

@app.post("/login")
@app.post("/auth/login")
@app.post("/api/v1/auth/login")
def login(credentials: dict = Body(...), db: Session = Depends(get_db)):
    email = credentials.get("email")
    password = credentials.get("password")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or user.password != password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    user_data = map_user_to_android(user, token=token)
    return {
        "success": True,
        "message": "Login successful",
        "user": user_data,
        "token": token,
        **user_data
    }

@app.post("/admin/login")
@app.post("/api/v1/admin/login")
def admin_login(credentials: dict = Body(...), db: Session = Depends(get_db)):
    email = credentials.get("email")
    password = credentials.get("password")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or user.password != password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if user.role not in ["ADMIN", "MODERATOR"]:
        raise HTTPException(status_code=403, detail="Admin access denied: Regular users are not permitted here")

    token = create_access_token({"sub": str(user.id), "role": user.role})
    user_data = map_user_to_android(user, token=token)
    return {
        "success": True,
        "message": "Admin login successful",
        "user": user_data,
        "token": token,
        **user_data
    }

signup_otps = {}

@app.post("/send-signup-otp")
def send_signup_otp(data: dict = Body(...), db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    signup_otps[email] = {
        "otp": otp,
        "expires": datetime.now() + timedelta(minutes=5)
    }
    
    send_otp_email(email, otp)
    return {"success": True, "message": "Verification code sent to your email"}

@app.post("/signup")
@app.post("/auth/signup")
@app.post("/api/v1/auth/signup")
def signup(data: dict = Body(...), db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    otp = data.get("otp", "").strip()
    if not otp:
        raise HTTPException(status_code=400, detail="OTP is required")
        
    otp_data = signup_otps.get(email)
    if not otp_data or otp_data["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if datetime.now() > otp_data["expires"]:
        del signup_otps[email]
        raise HTTPException(status_code=400, detail="OTP expired")
        
    del signup_otps[email]
    new_user = models.User(
        email=email,
        password=data.get("password"),
        fullName=data.get("name") or data.get("fullName") or "Rescuer",
        phoneNumber=data.get("phone") or data.get("phoneNumber") or "",
        mpin=data.get("mpin"),
        securityAnswer=data.get("securityAnswer").strip().lower() if data.get("securityAnswer") else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_data = map_user_to_android(new_user)
    return {
        "success": True,
        "message": "Registration successful",
        "user": user_data,
        **user_data
    }

@app.post("/login-mpin")
@app.post("/auth/login-mpin")
@app.post("/api/v1/auth/login-mpin")
def login_mpin(credentials: dict = Body(...), db: Session = Depends(get_db)):
    email = credentials.get("email", "").strip().lower()
    mpin  = credentials.get("mpin", "").strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="No account found with this email")
    if not user.mpin:
        raise HTTPException(status_code=400, detail="PIN not set. Please login with password.")
    if user.mpin != mpin:
        raise HTTPException(status_code=400, detail="Incorrect PIN. Try again.")
    token = create_access_token({"sub": str(user.id), "role": user.role})
    user_data = map_user_to_android(user, token=token)
    return {
        "success": True,
        "message": "Login successful",
        "user": user_data,
        "token": token,
        **user_data
    }

# ── Reset MPIN via Security Answer ──────────────────────────────────────────
@app.post("/reset-mpin")
def reset_mpin(data: dict = Body(...), db: Session = Depends(get_db)):
    email        = data.get("email", "").strip().lower()
    security_ans = data.get("securityAnswer", "").strip().lower()
    new_mpin     = data.get("newMpin", "").strip()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if not user.securityAnswer:
        raise HTTPException(status_code=400, detail="No security answer set for this account")
    if user.securityAnswer != security_ans:
        raise HTTPException(status_code=400, detail="Incorrect security answer")
    if len(new_mpin) != 4 or not new_mpin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
    user.mpin = new_mpin
    db.commit()
    return {"success": True, "message": "PIN reset successfully"}

@app.post("/verify-mpin")
def verify_mpin(data: dict = Body(...), db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    mpin = data.get("pin", "").strip() # VerifyPinRequest uses "pin" as field in Android app? Let's use both just in case
    if not mpin:
        mpin = data.get("mpin", "").strip()
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if not user.mpin:
        raise HTTPException(status_code=400, detail="Security PIN not set for this account")
    if user.mpin != mpin:
        raise HTTPException(status_code=400, detail="Incorrect Security PIN. Try again.")
    return {"success": True, "message": "PIN verified successfully"}

# 🔐 Reset Password via static Security PIN (mPIN)
@app.post("/reset-password-mpin")
def reset_password_mpin(data: dict = Body(...), db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    mpin = data.get("mpin", "").strip()
    new_password = data.get("newPassword", "").strip()
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if not user.mpin:
        raise HTTPException(status_code=400, detail="Security PIN not set for this account")
    if user.mpin != mpin:
        raise HTTPException(status_code=400, detail="Incorrect Security PIN. Try again.")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
    user.password = new_password
    db.commit()
    return {"success": True, "message": "Password reset successful"}

def send_otp_email(to_email: str, otp: str):
    import requests
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("SMTP_USER", "vemanisai@gmail.com") # Default to the verified Gmail

    # Fallback to local console log if API key is missing
    if not api_key:
        print(f"[Fallback Log] BREVO_API_KEY is missing in env. OTP for {to_email}: {otp}")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #030712; color: #e5e7eb; padding: 30px; text-align: center;">
        <div style="max-width: 500px; margin: 0 auto; background-color: #0f172a; padding: 30px; border-radius: 20px; border: 1px solid #1f2937;">
          <h2 style="color: #10b981; margin-bottom: 20px;">FoodRescue Verification</h2>
          <p>Use the following 6-digit OTP code to verify your account:</p>
          <div style="font-size: 28px; font-weight: bold; background-color: #111827; padding: 15px; margin: 20px auto; width: 160px; border-radius: 12px; border: 1px solid #10b981; color: #10b981; letter-spacing: 4px;">
            {otp}
          </div>
          <p style="color: #9ca3af; font-size: 12px; margin-top: 30px;">This code will expire in 5 minutes. If you did not request this, please ignore this email.</p>
        </div>
      </body>
    </html>
    """

    payload = {
        "sender": {"name": "FoodRescue", "email": sender_email},
        "to": [{"email": to_email}],
        "subject": "Your Verification Code",
        "htmlContent": html
    }
    
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        print(f"OTP Email sent successfully to {to_email} via Brevo HTTP API")
    except Exception as e:
        print(f"[Error] Failed to send email to {to_email} via Brevo: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[Error Details] {e.response.text}")

@app.post("/forgot-password")
def forgot_password(req: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    # Generate 6-digit OTP
    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    user.otpCode = otp
    user.otpExpiry = (datetime.now() + timedelta(minutes=5)).isoformat()

    db.commit()
    
    # Send actual email to user
    send_otp_email(req.email, otp)
    
    return {"success": True, "message": "OTP sent successfully to your email"}

@app.post("/verify-otp")
def verify_otp(req: schemas.VerifyOtpRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.otpCode != req.otp:
        return {"success": False, "message": "Invalid OTP"}

    expiry = datetime.fromisoformat(user.otpExpiry)
    if datetime.now() > expiry:
        return {"success": False, "message": "OTP has expired"}

    return {"success": True, "message": "OTP verified successfully"}

@app.post("/reset-password")
def reset_password(req: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.otpCode != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP verification")

    user.password = req.new_password # In production, hash it!
    user.otpCode = None
    user.otpExpiry = None
    db.commit()

    return {"success": True, "message": "Password reset successful"}

@app.post("/auth/google", response_model=schemas.AuthResponse)
def google_auth(req: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    # In a real app, verify the idToken with Google's API
    user = db.query(models.User).filter(models.User.email == req.email).first()

    if not user:
        user = models.User(
            email=req.email,
            fullName=req.fullName,
            password="google-auth-pwd", # Placeholder
            provider="Google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "success": True,
        "message": "Google login successful",
        "user": user,
        "token": req.idToken
    }

import time

def parse_time_to_ms(dt_str):
    if not dt_str:
        return int((time.time() + 7200) * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except:
            return int((time.time() + 7200) * 1000)

def parse_posted_at_to_ms(dt_str):
    if not dt_str:
        return int(time.time() * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        return int(time.time() * 1000)

def parse_ms_to_iso(ms):
    if not ms:
        return (datetime.now() + timedelta(hours=2)).isoformat()
    try:
        return datetime.fromtimestamp(ms / 1000.0).isoformat()
    except:
        return (datetime.now() + timedelta(hours=2)).isoformat()

def map_listing_to_android(listing):
    qty = 1
    unit = "Plates"
    if listing.quantity:
        parts = listing.quantity.strip().split(" ", 1)
        if parts:
            try:
                qty = int(parts[0])
            except ValueError:
                qty = 1
            if len(parts) > 1 and parts[1]:
                unit = str(parts[1])
    
    expiry_ms = parse_time_to_ms(listing.expiryTime)
    posted_ms = parse_posted_at_to_ms(listing.timestamp)
    
    status_str = "ACTIVE"
    if listing.status == "Claimed":
        status_str = "CLAIMED"
    db.commit()

    return {"success": True, "message": "Password reset successful"}

@app.post("/auth/google", response_model=schemas.AuthResponse)
def google_auth(req: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()

    if not user:
        user = models.User(
            email=req.email,
            fullName=req.fullName,
            password="google-auth-pwd",
            provider="Google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "success": True,
        "message": "Google login successful",
        "user": user,
        "token": req.idToken
    }

import time

def parse_time_to_ms(dt_str):
    if not dt_str:
        return int((time.time() + 7200) * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except:
            return int((time.time() + 7200) * 1000)

def parse_posted_at_to_ms(dt_str):
    if not dt_str:
        return int(time.time() * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        return int(time.time() * 1000)

def parse_ms_to_iso(ms):
    if not ms:
        return (datetime.now() + timedelta(hours=2)).isoformat()
    try:
        return datetime.fromtimestamp(ms / 1000.0).isoformat()
    except:
        return (datetime.now() + timedelta(hours=2)).isoformat()

def map_listing_to_android(listing):
    qty = 1
    unit = "Plates"
    if listing.quantity:
        parts = listing.quantity.strip().split(" ", 1)
        if parts:
            try:
                qty = int(parts[0])
            except ValueError:
                qty = 1
            if len(parts) > 1 and parts[1]:
                unit = str(parts[1])
    
    expiry_ms = parse_time_to_ms(listing.expiryTime)
    posted_ms = parse_posted_at_to_ms(listing.timestamp)
    
    status_str = "ACTIVE"
    if listing.status == "Claimed":
        status_str = "CLAIMED"
    elif listing.status == "Expired":
        status_str = "EXPIRED"
    elif listing.status == "Completed":
        status_str = "COMPLETED"
    elif listing.status == "On The Way":
        status_str = "ON_THE_WAY"
    elif listing.status == "Reached":
        status_str = "REACHED"
    elif listing.status == "Collected":
        status_str = "COLLECTED"
        
    p_name = "Rescuer"
    if listing.owner and listing.owner.fullName:
        p_name = str(listing.owner.fullName)

    f_name = "Rescue Food"
    if listing.title:
        f_name = str(listing.title)
        
    img_url = str(listing.imageUrl) if listing.imageUrl else ""
    image_list = []
    if img_url:
        if img_url.startswith("["):
            try:
                import json
                image_list = json.loads(img_url)
            except:
                image_list = [img_url]
        elif "," in img_url:
            image_list = [x.strip() for x in img_url.split(",")]
        else:
            image_list = [img_url]
    else:
        image_list = []

    return {
        "id": str(listing.id),
        "userId": str(listing.postedBy) if listing.postedBy else "1",
        "posterName": p_name,
        "posterRating": 5.0,
        "foodName": f_name,
        "description": str(listing.description) if listing.description else "",
        "quantity": qty,
        "unit": str(unit) if unit else "Plates",
        "foodType": "VEG" if (listing.category or "").upper() == "VEG" else "NON_VEG",
        "imageUrl": image_list[0] if image_list else "",
        "imageUrls": image_list,
        "latitude": listing.latitude or 13.0827,
        "longitude": listing.longitude or 80.2707,
        "address": str(listing.location) if listing.location else "Chennai",
        "distanceKm": 1.2,
        "expiryTime": expiry_ms,
        "postedAt": posted_ms,
        "status": status_str,
        "isSaved": False,
        "verificationOtp": listing.verification_otp or ""
    }

@app.get("/food-listings")
def get_food_listings(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    sort_by: Optional[str] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    current_user_id = None
    if authorization:
        try:
            payload = decode_access_token(authorization.split(" ")[1])
            if payload:
                current_user_id = int(payload.get("sub"))
        except:
            pass

    blocked_user_ids = []
    if current_user_id:
        blocked_user_ids = [b.blocked_id for b in db.query(models.UserBlock).filter(models.UserBlock.blocker_id == current_user_id).all()]

    listings = db.query(models.FoodListing).all()
    now = datetime.now()
    updated = False

    for listing in listings:
        if listing.status == "Available":
            try:
                expiry = datetime.fromisoformat(listing.expiryTime.replace("Z", "+00:00"))
                if now > expiry:
                    listing.status = "Expired"
                    updated = True
            except:
                pass

    if updated:
        db.commit()

    active_listings = [l for l in listings if l.status != "Expired" and l.postedBy not in blocked_user_ids]

    mapped_listings = []
    for l in active_listings:
        data = map_listing_to_android(l)
        dist = calculate_distance(l.latitude, l.longitude, lat, lng) if (lat is not None and lng is not None) else 1.2
        data["distanceKm"] = round(dist, 1)
        data["priorityScore"] = calculate_priority_score(l, lat, lng)
        mapped_listings.append(data)

    if sort_by == "urgency":
        mapped_listings.sort(key=lambda x: x["expiryTime"])
    elif sort_by == "distance":
        mapped_listings.sort(key=lambda x: x["distanceKm"])
    elif sort_by == "quantity":
        mapped_listings.sort(key=lambda x: x["quantity"], reverse=True)
    elif sort_by == "priority" or not sort_by:
        mapped_listings.sort(key=lambda x: x["priorityScore"], reverse=True)

    return mapped_listings

@app.post("/auth/google", response_model=schemas.AuthResponse)
def google_auth(req: schemas.GoogleAuthRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()

    if not user:
        user = models.User(
            email=req.email,
            fullName=req.fullName,
            password="google-auth-pwd",
            provider="Google"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "success": True,
        "message": "Google login successful",
        "user": user,
        "token": req.idToken
    }

import time

def parse_time_to_ms(dt_str):
    if not dt_str:
        return int((time.time() + 7200) * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except:
            return int((time.time() + 7200) * 1000)

def parse_posted_at_to_ms(dt_str):
    if not dt_str:
        return int(time.time() * 1000)
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except:
        return int(time.time() * 1000)

def parse_ms_to_iso(ms):
    if not ms:
        return (datetime.now() + timedelta(hours=2)).isoformat()
    try:
        return datetime.fromtimestamp(ms / 1000.0).isoformat()
    except:
        return (datetime.now() + timedelta(hours=2)).isoformat()

def map_listing_to_android(listing):
    qty = 1
    unit = "Plates"
    if listing._quantity:
        parts = str(listing._quantity).strip().split(" ", 1)
        if parts:
            try:
                qty = int(float(parts[0]))
            except (ValueError, TypeError):
                qty = 1
            if len(parts) > 1 and parts[1]:
                unit = str(parts[1])
    
    expiry_ms = parse_time_to_ms(listing.expiryTime)
    posted_ms = parse_posted_at_to_ms(listing.timestamp)
    
    status_str = "ACTIVE"
    if listing.status == "Claimed":
        status_str = "CLAIMED"
    elif listing.status == "Expired":
        status_str = "EXPIRED"
    elif listing.status == "Completed":
        status_str = "COMPLETED"
    elif listing.status == "On The Way":
        status_str = "ON_THE_WAY"
    elif listing.status == "Reached":
        status_str = "REACHED"
    elif listing.status == "Collected":
        status_str = "COLLECTED"
        
    p_name = "Rescuer"
    if listing.owner and listing.owner.fullName:
        p_name = str(listing.owner.fullName)

    f_name = "Rescue Food"
    if listing.title:
        f_name = str(listing.title)
        
    img_url = str(listing.imageUrl) if listing.imageUrl else ""
    image_list = []
    if img_url:
        if img_url.startswith("["):
            try:
                import json
                image_list = json.loads(img_url)
            except:
                image_list = [img_url]
        elif "," in img_url:
            image_list = [x.strip() for x in img_url.split(",")]
        else:
            image_list = [img_url]
    else:
        image_list = []

    return {
        "id": str(listing.id),
        "userId": str(listing.postedBy) if listing.postedBy else "1",
        "posterName": p_name,
        "posterRating": 5.0,
        "foodName": f_name,
        "description": str(listing.description) if listing.description else "",
        "quantity": qty,
        "unit": str(unit) if unit else "Plates",
        "foodType": "VEG" if (listing.category or "").upper() == "VEG" else "NON_VEG",
        "imageUrl": image_list[0] if image_list else "",
        "imageUrls": image_list,
        "latitude": listing.latitude or 13.0827,
        "longitude": listing.longitude or 80.2707,
        "address": str(listing.location) if listing.location else "Chennai",
        "distanceKm": 1.2,
        "expiryTime": expiry_ms,
        "postedAt": posted_ms,
        "status": status_str,
        "isSaved": False,
        "verificationOtp": listing.verification_otp or ""
    }

@app.get("/food-listings")
def get_food_listings(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    sort_by: Optional[str] = None,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    current_user_id = None
    if authorization:
        try:
            payload = decode_access_token(authorization.split(" ")[1])
            if payload:
                current_user_id = int(payload.get("sub"))
        except:
            pass

    blocked_user_ids = []
    if current_user_id:
        blocked_user_ids = [b.blocked_id for b in db.query(models.UserBlock).filter(models.UserBlock.blocker_id == current_user_id).all()]

    listings = db.query(models.FoodListing).all()
    now = datetime.now()
    updated = False

    for listing in listings:
        if listing.status == "Available":
            try:
                expiry = datetime.fromisoformat(listing.expiryTime.replace("Z", "+00:00"))
                if now > expiry:
                    listing.status = "Expired"
                    updated = True
            except:
                pass

    if updated:
        db.commit()

    active_listings = [l for l in listings if l.status != "Expired" and l.postedBy not in blocked_user_ids]

    mapped_listings = []
    for l in active_listings:
        data = map_listing_to_android(l)
        dist = calculate_distance(l.latitude, l.longitude, lat, lng) if (lat is not None and lng is not None) else 1.2
        data["distanceKm"] = round(dist, 1)
        data["priorityScore"] = calculate_priority_score(l, lat, lng)
        mapped_listings.append(data)

    if sort_by == "urgency":
        mapped_listings.sort(key=lambda x: x["expiryTime"])
    elif sort_by == "distance":
        mapped_listings.sort(key=lambda x: x["distanceKm"])
    elif sort_by == "quantity":
        mapped_listings.sort(key=lambda x: x["quantity"], reverse=True)
    elif sort_by == "priority" or not sort_by:
        mapped_listings.sort(key=lambda x: x["priorityScore"], reverse=True)

    return mapped_listings

@app.get("/food-listings/recommendations")
def get_recommendations(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    user = None
    if authorization:
        try:
            payload = decode_access_token(authorization.split(" ")[1])
            if payload:
                user = db.query(models.User).filter(models.User.id == payload.get("sub")).first()
        except:
            pass

    listings = db.query(models.FoodListing).filter(models.FoodListing.status == "Available").all()
    if not user:
        sorted_listings = sorted(listings, key=lambda l: calculate_priority_score(l), reverse=True)
        return [map_listing_to_android(l) for l in sorted_listings[:5]]

    past_rescues = db.query(models.FoodListing).filter(models.FoodListing.claimedBy == user.id).all()
    fav_category = "Veg"
    if past_rescues:
        veg_count = sum(1 for r in past_rescues if r.category == "Veg")
        non_veg_count = len(past_rescues) - veg_count
        if non_veg_count > veg_count:
            fav_category = "Non-Veg"

    recommendations = []
    for l in listings:
        score = calculate_priority_score(l)
        if l.category == fav_category:
            score += 20
        recommendations.append((l, score))

    recommendations.sort(key=lambda x: x[1], reverse=True)
    return [map_listing_to_android(x[0]) for x in recommendations[:5]]

@app.get("/food-listings/{listing_id}")
def get_listing_by_id(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return map_listing_to_android(listing)

@app.post("/api/v1/food/listings")
@app.post("/post-food")
def post_food(data: dict = Body(...), db: Session = Depends(get_db)):
    qty = data.get("quantity", 1)
    unit = data.get("unit", "Plates")
    quantity_str = f"{qty} {unit}"
    expiry_ms = data.get("expiryTime", 0)
    expiry_str = parse_ms_to_iso(expiry_ms)
    posted_ms = data.get("postedAt", 0)
    posted_str = parse_ms_to_iso(posted_ms)

    image_url_val = ""
    if data.get("imageUrls"):
        image_url_val = ",".join(data.get("imageUrls"))
    else:
        image_url_val = data.get("imageUrl", "")

    new_listing = models.FoodListing(
        title=data.get("foodName", "Rescue Food"),
        description=data.get("description", ""),
        quantity=quantity_str,
        expiryTime=expiry_str,
        location=data.get("address", "Chennai"),
        imageUrl=image_url_val,
        postedBy=int(data.get("userId")) if data.get("userId") else 1,
        status="Available",
        category="Veg" if data.get("foodType") == "VEG" else "Non-Veg",
        timestamp=posted_str,
        latitude=float(data.get("latitude", 13.0827)),
        longitude=float(data.get("longitude", 80.2707))
    )
    db.add(new_listing)

    user = db.query(models.User).filter(models.User.id == new_listing.postedBy).first()
    if user:
        user.donationsCount += 1
        user.points += 10
        user.level = 1 + (user.points // 100)

    db.commit()
    db.refresh(new_listing)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast({
                "type": "NEW_POST",
                "title": "New Food Available Nearby!",
                "message": f"{new_listing.title} is available at {new_listing.location}.",
                "listing": map_listing_to_android(new_listing)
            }))
    except Exception:
        pass

    return map_listing_to_android(new_listing)

@app.post("/claim-food/{listing_id}")
def claim_food(listing_id: int, data: dict = Body(None), db: Session = Depends(get_db)):
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "Available":
        raise HTTPException(status_code=400, detail="Listing is not available")

    user_id = 1
    if data:
        user_id = data.get("userId") or data.get("user_id") or 1

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    listing.status = "Claimed"
    listing.claimedBy = user_id
    listing.verification_otp = otp
    listing.claimed_at = datetime.utcnow()

    new_notif = models.Notification(
        userId=listing.postedBy,
        title="Food Claimed!",
        message=f"Someone has accepted your donation: {listing.title}",
        type="CLAIMED",
        timestamp=datetime.now().isoformat()
    )
    db.add(new_notif)
    db.commit()
    db.refresh(listing)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.send_personal_message({
                "type": "CLAIMED",
                "title": new_notif.title,
                "message": new_notif.message,
                "timestamp": new_notif.timestamp,
                "id": new_notif.id
            }, str(listing.postedBy)))
            loop.create_task(manager.broadcast({
                "type": "STATUS_UPDATE",
                "listing_id": str(listing.id),
                "status": "Claimed"
            }))
    except Exception:
        pass

    return {
        "postId": str(listing.id),
        "userId": str(user_id),
        "claimedAt": int(time.time() * 1000),
        "verification_otp": otp
    }

@app.delete("/food-listings/{listing_id}/save")
def unsave_listing_stub(listing_id: int):
    return {"success": True}

@app.post("/cancel-rescue/{listing_id}", response_model=schemas.FoodListing)
def cancel_rescue(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.status = "Available"
    listing.claimedBy = None

    db.commit()
    db.refresh(listing)
    return listing

@app.get("/user/{user_id}")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return map_user_to_android(user)
@app.post("/user/{user_id}/update-mpin")
def update_user_mpin(user_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    mpin = data.get("mpin", "").strip()
    security_answer = data.get("securityAnswer", "").strip().lower()
    
    if len(mpin) != 4 or not mpin.isdigit():
        raise HTTPException(status_code=400, detail="PIN must be exactly 4 digits")
        
    user.mpin = mpin
    if security_answer:
        user.securityAnswer = security_answer
        
    db.commit()
    return {"success": True, "message": "Security PIN updated successfully", "user": user}

@app.put("/user/{user_id}")
def update_user_profile(user_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if "fullName" in data:
        user.fullName = data["fullName"].strip()
    if "phoneNumber" in data:
        user.phoneNumber = data["phoneNumber"].strip()
        
    db.commit()
    db.refresh(user)
    return {
        "success": True,
        "message": "Profile updated successfully",
        "user": map_user_to_android(user)
    }

@app.post("/update-rescue-status/{listing_id}", response_model=schemas.FoodListing)
def update_status(listing_id: int, status: str = Body(..., embed=True), db: Session = Depends(get_db)):
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.status = status

    # If completed, update user stats
    if status == "Completed":
        user = db.query(models.User).filter(models.User.id == listing.claimedBy).first()
        if user:
            user.rescuesCount += 1
            user.totalCarbonSaved += listing.carbonSaved
            user.points += 50 # Base points for completion

        # Notify Donor that rescue is complete
        new_notif = models.Notification(
            userId=listing.postedBy,
            title="Rescue Successful! ❤️",
            message=f"Your donation of {listing.title} has been successfully delivered.",
            type="COMPLETED",
            timestamp=datetime.now().isoformat()
        )
        db.add(new_notif)
    elif status == "On The Way":
        # Notify Donor that someone is coming
        new_notif = models.Notification(
            userId=listing.postedBy,
            title="Rescuer On The Way! 🚀",
            message=f"A volunteer is coming to pick up: {listing.title}",
            type="STATUS_UPDATE",
            timestamp=datetime.now().isoformat()
        )
        db.add(new_notif)

    db.commit()
    db.refresh(listing)
    return listing


@app.get("/notifications/{user_id}", response_model=List[schemas.Notification])
def get_notifications(user_id: int, db: Session = Depends(get_db)):
    return db.query(models.Notification).filter(models.Notification.userId == user_id).order_by(models.Notification.id.desc()).all()

@app.put("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(models.Notification).filter(models.Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.isRead = True
    db.commit()
    return {"success": True}

@app.put("/notifications/read-all/{user_id}")
def mark_all_notifications_read(user_id: int, db: Session = Depends(get_db)):
    db.query(models.Notification).filter(models.Notification.userId == user_id).update({models.Notification.isRead: True})
    db.commit()
    return {"success": True}

@app.get("/user/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    active_posts = db.query(models.FoodListing).filter(
        models.FoodListing.postedBy == user_id,
        models.FoodListing.status == "Available"
    ).count()

    nearby_count = db.query(models.FoodListing).filter(
        models.FoodListing.status == "Available"
    ).count()

    return {
        "mealsSaved": (user.rescuesCount or 0) * 2,
        "activePosts": active_posts,
        "nearbyCount": nearby_count,
        "rescuersCount": db.query(models.User).count()
    }

@app.get("/community-stats")
def get_community_stats(db: Session = Depends(get_db)):
    total_rescues = db.query(func.sum(models.User.rescuesCount)).scalar() or 0
    total_donations = db.query(func.sum(models.User.donationsCount)).scalar() or 0
    active_users = db.query(models.User).count()
    active_posts = db.query(models.FoodListing).filter(models.FoodListing.status == "Available").count()

    return {
        "mealsSaved": (total_rescues + total_donations) * 2,
        "activePosts": active_posts,
        "nearbyCount": active_posts,
        "rescuersCount": active_users
    }

@app.get("/impact-stats")
def get_impact_stats(db: Session = Depends(get_db)):
    stats = get_community_stats(db)
    return {
        "mealsSaved": stats["mealsSaved"],
        "co2Reduced": stats["mealsSaved"] * 2.0,
        "peopleFed": stats["mealsSaved"],
        "volunteersActive": stats["rescuersCount"]
    }

@app.post("/api/food/upload-image")
def upload_image(request: Request, file: UploadFile = File(...)):
    # Validate file type extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed.")
    
    # Read file content to check file size (max 5MB)
    contents = file.file.read()
    size = len(contents)
    if size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum limit of 5MB.")
    
    # Seek back to 0 just in case
    file.file.seek(0)
    
    # Generate unique filename using UUID + timestamp
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex
    filename = f"{unique_id}_{timestamp}{ext}"
    
    # Save the file to our target upload directory
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(contents)
        
    base_url = str(request.base_url).rstrip('/')
    image_url = f"{base_url}/uploads/food_images/{filename}"
    return {
        "success": True,
        "image_url": image_url,
        "message": "Image uploaded successfully"
    }

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)

@app.post("/api/food/upload-images")
def upload_images(request: Request, files: List[UploadFile] = File(...)):
    urls = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png"]:
            raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed.")
        contents = file.file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds maximum limit of 5MB.")
        file.file.seek(0)
        timestamp = int(time.time())
        unique_id = uuid.uuid4().hex
        filename = f"{unique_id}_{timestamp}{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(contents)
        base_url = str(request.base_url).rstrip('/')
        image_url = f"{base_url}/uploads/food_images/{filename}"
        urls.append(image_url)
    return {"success": True, "image_urls": urls}



@app.post("/verify-pickup/{listing_id}")
def verify_pickup(listing_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    otp = data.get("otp", "").strip()
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.verification_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    listing.status = "Completed"
    
    rescuer = db.query(models.User).filter(models.User.id == listing.claimedBy).first()
    if rescuer:
        rescuer.rescuesCount += 1
        rescuer.points += 50
        rescuer.level = 1 + (rescuer.points // 100)
        check_and_award_badges(rescuer, db)

    donor = db.query(models.User).filter(models.User.id == listing.postedBy).first()
    if donor:
        donor.points += 20
        donor.level = 1 + (donor.points // 100)
        check_and_award_badges(donor, db)

    new_notif = models.Notification(
        userId=listing.postedBy,
        title="Rescue Completed! ❤️",
        message=f"Your donation of {listing.title} has been successfully delivered.",
        type="COMPLETED",
        timestamp=datetime.now().isoformat()
    )
    db.add(new_notif)
    db.commit()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.send_personal_message({
                "type": "COMPLETED",
                "title": new_notif.title,
                "message": new_notif.message,
                "timestamp": new_notif.timestamp
            }, str(listing.postedBy)))
            loop.create_task(manager.broadcast({
                "type": "STATUS_UPDATE",
                "listing_id": str(listing.id),
                "status": "Completed"
            }))
    except Exception:
        pass

    return {"success": True, "message": "Pickup verified and rescue completed successfully"}

def check_and_award_badges(user, db):
    standard_badges = [
        {"name": "First Hero", "description": "Completed your first rescue", "icon": "shield-check", "xp": 50},
        {"name": "Eco Savior", "description": "Saved 5 or more meals", "icon": "leaf", "xp": 250},
        {"name": "Super Donor", "description": "Donated 5 or more times", "icon": "gift", "xp": 200},
    ]
    for sb in standard_badges:
        badge = db.query(models.Badge).filter(models.Badge.name == sb["name"]).first()
        if not badge:
            badge = models.Badge(name=sb["name"], description=sb["description"], icon=sb["icon"], xp_required=sb["xp"])
            db.add(badge)
            db.commit()
            db.refresh(badge)

    if user.rescuesCount >= 1:
        award_badge(user.id, "First Hero", db)
    if user.rescuesCount >= 5:
        award_badge(user.id, "Eco Savior", db)
    if user.donationsCount >= 5:
        award_badge(user.id, "Super Donor", db)

def award_badge(user_id, badge_name, db):
    badge = db.query(models.Badge).filter(models.Badge.name == badge_name).first()
    if not badge:
        return
    existing = db.query(models.UserBadge).filter(models.UserBadge.user_id == user_id, models.UserBadge.badge_id == badge.id).first()
    if not existing:
        ub = models.UserBadge(user_id=user_id, badge_id=badge.id)
        db.add(ub)
        notif = models.Notification(
            userId=user_id,
            title="Badge Unlocked! 🏆",
            message=f"Congratulations! You've unlocked the '{badge_name}' badge.",
            type="BADGE_UNLOCK",
            timestamp=datetime.now().isoformat()
        )
        db.add(notif)
        db.commit()

@app.post("/submit-rating")
def submit_rating(data: schemas.RatingCreate, authorization: str = Header(...), db: Session = Depends(get_db)):
    payload = decode_access_token(authorization.split(" ")[1])
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rater_id = int(payload.get("sub"))
    
    new_rating = models.Rating(
        rater_user_id=rater_id,
        rated_user_id=data.rated_user_id,
        rating=data.rating
    )
    db.add(new_rating)
    db.commit()
    return {"success": True, "message": "Rating submitted successfully"}

@app.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    top_rescuers = db.query(models.User).order_by(models.User.rescuesCount.desc()).limit(10).all()
    top_donors = db.query(models.User).order_by(models.User.donationsCount.desc()).limit(10).all()
    return {
        "rescuers": [
            {"id": u.id, "fullName": u.fullName or u.email, "points": u.points, "rescuesCount": u.rescuesCount, "level": u.level}
            for u in top_rescuers
        ],
        "donors": [
            {"id": u.id, "fullName": u.fullName or u.email, "points": u.points, "donationsCount": u.donationsCount, "level": u.level}
            for u in top_donors
        ]
    }

@app.get("/user/{user_id}/badges")
def get_user_badges(user_id: int, db: Session = Depends(get_db)):
    badges = db.query(models.Badge).join(models.UserBadge, models.UserBadge.badge_id == models.Badge.id).filter(models.UserBadge.user_id == user_id).all()
    return [
        {"id": b.id, "name": b.name, "description": b.description, "icon": b.icon, "xp_required": b.xp_required}
        for b in badges
    ]

@app.post("/report")
def create_report(data: schemas.ReportCreate, authorization: str = Header(...), db: Session = Depends(get_db)):
    payload = decode_access_token(authorization.split(" ")[1])
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    reporter_id = int(payload.get("sub"))
    
    new_report = models.Report(
        reporter_id=reporter_id,
        reported_user_id=data.reported_user_id,
        reported_listing_id=data.reported_listing_id,
        reason=data.reason
    )
    db.add(new_report)
    db.commit()
    return {"success": True, "message": "Report submitted successfully"}

@app.post("/block/{user_id}")
def block_user(user_id: int, authorization: str = Header(...), db: Session = Depends(get_db)):
    payload = decode_access_token(authorization.split(" ")[1])
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    blocker_id = int(payload.get("sub"))
    
    existing = db.query(models.UserBlock).filter(models.UserBlock.blocker_id == blocker_id, models.UserBlock.blocked_id == user_id).first()
    if not existing:
        block = models.UserBlock(blocker_id=blocker_id, blocked_id=user_id)
        db.add(block)
        db.commit()
    return {"success": True, "message": "User blocked successfully"}

@app.get("/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_users = db.query(models.User).count()
    total_listings = db.query(models.FoodListing).count()
    total_completed = db.query(models.FoodListing).filter(models.FoodListing.status == "Completed").count()
    total_reports = db.query(models.Report).count()
    return {
        "totalUsers": total_users,
        "totalListings": total_listings,
        "totalCompletedRescues": total_completed,
        "totalReports": total_reports
    }

@app.get("/admin/reports")
def get_admin_reports(db: Session = Depends(get_db)):
    reports = db.query(models.Report).all()
    results = []
    for r in reports:
        reporter = db.query(models.User).filter(models.User.id == r.reporter_id).first()
        listing = db.query(models.FoodListing).filter(models.FoodListing.id == r.reported_listing_id).first() if r.reported_listing_id else None
        results.append({
            "id": r.id,
            "reporterName": reporter.fullName if reporter else "Anonymous",
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "listingTitle": listing.title if listing else None,
            "listingId": r.reported_listing_id
        })
    return results

@app.post("/admin/resolve-report/{report_id}")
def resolve_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "Resolved"
    db.commit()
    return {"success": True, "message": "Report resolved successfully"}

@app.post("/admin/listing/{listing_id}/action")
def admin_listing_action(listing_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    action = data.get("action", "")
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if action == "delete":
        db.delete(listing)
        db.commit()
        return {"success": True, "message": "Listing deleted successfully"}
    elif action == "approve":
        listing.status = "Available"
        db.commit()
        return {"success": True, "message": "Listing approved successfully"}
    return {"success": False, "message": "Invalid action"}

@app.post("/admin/user/{user_id}/action")
def admin_user_action(user_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    action = data.get("action", "")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if action == "warn":
        user.warningCount += 1
        user.status = "Warning"
        db.commit()
        return {"success": True, "message": "User warned successfully"}
    elif action == "ban":
        user.isBanned = True
        user.status = "Banned"
        db.commit()
        return {"success": True, "message": "User banned successfully"}
    return {"success": False, "message": "Invalid action"}
@app.post("/api/v1/verify-food-image")
async def verify_food_image(request: Request):
    # Mock AI/Moderation check for image originality
    data = await request.json()
    image_url = data.get("imageUrl", "")
    
    # In a real production environment, this would call a Vision API or a trained model
    # For now, we will simulate an authentic response.
    return {
        "isOriginal": True,
        "confidence": 0.94,
        "message": "Original food image detected."
    }
