import bcrypt
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.models import User
from app.database import SessionLocal


# Secret key for JWT - in production, use environment variable
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """Verify a JWT token and return the payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


security = HTTPBearer()

import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a key if it doesn't exist for development
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    with open(".env", "a") as f:
        f.write(f"\nENCRYPTION_KEY={ENCRYPTION_KEY}")

def get_current_user(auth: HTTPAuthorizationCredentials = Depends(security)):
    """Get the current user from the token"""
    token = auth.credentials
    payload = verify_token(token)
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def authenticate_user(email: str, password: str):
    """Authenticate a user by email and password"""
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    db.close()
    
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def has_permission(user, permission: str) -> bool:
    """Check if user has a specific permission based on role"""
    # Define permissions for each role
    role_permissions = {
        "admin": [
            "register_user", "enroll_face", "view_attendance", 
            "view_dashboard", "view_users", "manage_system"
        ],
        "manager": [
            "enroll_face", "view_attendance", "view_dashboard", "view_users"
        ],
        "employee": [
            "view_dashboard", "view_attendance"
        ],
        "user": [  # Backward compatibility for existing DB entries
            "view_dashboard", "view_attendance"
        ]
    }
    
    user_permissions = role_permissions.get(user.role, [])
    return permission in user_permissions