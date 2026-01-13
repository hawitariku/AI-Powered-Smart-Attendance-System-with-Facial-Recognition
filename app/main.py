from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
import numpy as np


from app.database import Base, engine, SessionLocal
from app.models import User, FaceEmbedding, Attendance
from app.face_utils import get_embedding
from app.auth import authenticate_user, create_access_token, get_current_user, has_permission, get_password_hash
import cv2
import threading
import time
import base64
import io
from PIL import Image
from app.camera import RemoteFaceProcessor

# Global variable to control attendance system
attendance_system_running = False
attendance_system_thread = None

# Store session processors per user
remote_face_sessions = {}


def run_attendance_system():
    """Run the attendance system in a separate thread"""
    global attendance_system_running
    
    # Import the attendance function
    from app.camera import recognize_and_mark
    
    # Run the attendance system
    try:
        recognize_and_mark()
    except Exception as e:
        print(f"Error in attendance system: {e}")
    finally:
        attendance_system_running = False


Base.metadata.create_all(bind=engine)


app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint to get access token"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"user_id": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current user's info for the dashboard"""
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }


@app.post("/register")
def register(name: str = Form(...), email: str = Form(...), password: str = Form(...), current_user: User = Depends(get_current_user)):
    """Register a new user - requires authentication and permission"""
    # Check if current user has permission to register users
    if not has_permission(current_user, "register_user"):
        raise HTTPException(status_code=403, detail="Not authorized to register users")
    
    db = SessionLocal()
    # Check if user with this email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user = User(name=name, email=email, password_hash=get_password_hash(password))
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return {"message": f"User registered with ID: {user_id}"}


@app.post("/enroll/{user_id}")
async def enroll_face(user_id: int, current_user: User = Depends(get_current_user)):
    """Enroll face with liveness verification"""
    if not has_permission(current_user, "enroll_face"):
        raise HTTPException(status_code=403, detail="Not authorized to enroll faces")
    
    # Verify that the user_id exists
    db = SessionLocal()
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    db.close()
    
    # Stop any running attendance system
    global attendance_system_running
    if attendance_system_running:
        attendance_system_running = False
        time.sleep(1)
    
    # Start enrollment in a separate thread
    from app.camera import recognize_and_mark
    import threading
    
    enrollment_thread = threading.Thread(target=recognize_and_mark, args=(user_id,))
    enrollment_thread.daemon = True
    enrollment_thread.start()
    
    return {"status": "started", "message": "Secured Enrollment Session Started..."}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard endpoint"""
    return templates.TemplateResponse("dashboard.html", {"request": request})



@app.get("/login_page", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/debug-logs")
def get_debug_logs(current_user: User = Depends(get_current_user)):
    """Fetch debug logs for the web console"""
    log_file = "debug_live.log"
    import os
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return {"logs": f.read()}
    return {"logs": "Waiting for system to start..."}

@app.get("/users")
def list_users(current_user: User = Depends(get_current_user)):
    """List all users for the dashboard"""
    if not has_permission(current_user, "view_users"):
        raise HTTPException(status_code=403, detail="Not authorized to view users")
    db = SessionLocal()
    users = db.query(User).all()
    user_data = []
    from app.models import FaceEmbedding
    for u in users:
        has_face = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == u.id).first() is not None
        user_data.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "has_face": has_face
        })
    db.close()
    return user_data

@app.get("/attendance-data")
def get_attendance_data(current_user: User = Depends(get_current_user)):
    """Get all attendance records for the dashboard"""
    if not has_permission(current_user, "view_attendance"):
        raise HTTPException(status_code=403, detail="Not authorized to view attendance")
    
    db = SessionLocal()
    
    # Filter records based on role
    if current_user.role in ["employee", "user"]:
        records = db.query(Attendance).filter(Attendance.user_id == current_user.id).all()
    else:
        records = db.query(Attendance).all()
    data = []
    for r in records:
        user = db.query(User).filter(User.id == r.user_id).first()
        data.append({
            "user_id": r.user_id,
            "name": user.name if user else "Unknown",
            "date": str(r.date),
            "time": str(r.time),
            "status": r.status
        })
    db.close()
    return data

@app.post("/start_attendance")
def start_attendance(current_user: User = Depends(get_current_user)):
    """Start attendance system"""
    if not has_permission(current_user, "manage_system"):
        raise HTTPException(status_code=403, detail="Not authorized to manage system")
    
    global attendance_system_running, attendance_system_thread
    if attendance_system_running:
        return {"message": "Attendance system is already running"}
    attendance_system_running = True
    attendance_system_thread = threading.Thread(target=run_attendance_system)
    attendance_system_thread.daemon = True
    attendance_system_thread.start()
    return {"message": "Attendance system started successfully."}

@app.post("/stop_attendance")
def stop_attendance(current_user: User = Depends(get_current_user)):
    """Stop attendance system"""
    if not has_permission(current_user, "manage_system"):
        raise HTTPException(status_code=403, detail="Not authorized to manage system")
    
    global attendance_system_running
    attendance_system_running = False
    return {"message": "Attendance system stopped successfully"}

@app.get("/face-status")
def get_face_status(current_user: User = Depends(get_current_user)):
    """Check if the current user has a face enrolled"""
    db = SessionLocal()
    has_face = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == current_user.id).first() is not None
    db.close()
    return {"has_face": has_face}


@app.post("/reset-face")
def reset_face(user_id: int, current_user: User = Depends(get_current_user)):
    """Admin/Manager tool to clear a user's face record"""
    if not has_permission(current_user, "manage_system"):
        raise HTTPException(status_code=403, detail="Not authorized to reset faces")
    
    db = SessionLocal()
    db.query(FaceEmbedding).filter(FaceEmbedding.user_id == user_id).delete()
    db.commit()
    db.close()
    return {"message": f"Biometric data for user {user_id} has been cleared."}


@app.post("/process-remote-frame")
async def process_remote_frame(request: Request, current_user: User = Depends(get_current_user)):
    """Process a single frame from the browser for remote check-in"""
    data = await request.json()
    image_data = data.get("image")
    mode = data.get("mode", "ATTEND") # "ENROLL" or "ATTEND"
    
    if not image_data:
        raise HTTPException(status_code=400, detail="Missing image data")

    # Hardening: Prevent employees from overwriting enrolled face
    if mode == "ENROLL" and current_user.role in ["employee", "user"]:
        db = SessionLocal()
        existing = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == current_user.id).first()
        db.close()
        if existing:
            raise HTTPException(status_code=403, detail="Biometrics already enrolled. Contact Admin for reset.")

    # Get or create processor for this user
    if current_user.id not in remote_face_sessions:
        remote_face_sessions[current_user.id] = RemoteFaceProcessor()
    
    processor = remote_face_sessions[current_user.id]
    
    # Decode base64 image
    try:
        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = np.array(img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")

    # Process
    result = processor.process_frame(frame, current_user.id, mode=mode)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
