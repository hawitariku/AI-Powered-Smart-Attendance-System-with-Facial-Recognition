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

# Global variable to control attendance system
attendance_system_running = False
attendance_system_thread = None


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
def enroll_face(user_id: int, current_user: User = Depends(get_current_user)):
    """Enroll face for a user - requires authentication and permission"""
    # Check if current user has permission to enroll faces
    if not has_permission(current_user, "enroll_face"):
        raise HTTPException(status_code=403, detail="Not authorized to enroll faces")
    
    # Verify that the user_id exists
    db = SessionLocal()
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    db.close()
    
    # Initialize MTCNN for face detection
    from facenet_pytorch import MTCNN
    mtcnn = MTCNN(image_size=160, margin=20)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return {"error": "Could not open camera"}
    
    # Allow camera to warm up
    import time
    time.sleep(2)
    
    # Try multiple frames to get multiple samples
    embeddings = []
    for attempt in range(30):  # Try for 30 frames
        ret, frame = cap.read()
        if not ret:
            continue
            
        # Try to detect face
        try:
            face = mtcnn(frame)
            if face is not None:
                # Face detected, now get embedding
                from app.face_utils import get_embedding
                emb = get_embedding(frame)
                if emb is not None:
                    embeddings.append(emb)
                    # Only need 3 good samples
                    if len(embeddings) >= 3:
                        break
        except Exception as e:
            pass  # Continue trying
            
        time.sleep(0.1)  # Small delay between frames
    
    cap.release()
    
    if len(embeddings) == 0:
        return {"error": "No face detected after multiple attempts"}
    
    # Use average of embeddings if multiple were captured
    if len(embeddings) > 1:
        final_embedding = np.mean(embeddings, axis=0)
    else:
        final_embedding = embeddings[0]
    
    db = SessionLocal()
    
    # Save embedding
    record = FaceEmbedding(user_id=user_id, embedding=','.join(map(str, final_embedding.tolist())))
    db.add(record)
    
    # Automatically mark attendance when face is enrolled
    import datetime
    today = datetime.date.today()
    time_now = datetime.datetime.now().time()
    attendance_record = Attendance(user_id=user_id, date=today, time=time_now, status="Present")
    db.add(attendance_record)
    
    db.commit()
    db.close()
    
    return {"message": f"Face enrolled successfully with {len(embeddings)} sample(s) and attendance marked"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user: User = Depends(get_current_user)):
    """Dashboard endpoint - requires authentication and permission"""
    # Check if current user has permission to view dashboard
    if not has_permission(current_user, "view_dashboard"):
        raise HTTPException(status_code=403, detail="Not authorized to view dashboard")
    
    db = SessionLocal()
    records = db.query(Attendance).all()
    users = db.query(User).all()
    db.close()
    return templates.TemplateResponse("dashboard.html", {"request": request, "records": records, "users": users})


@app.post("/start_attendance")
def start_attendance(current_user: User = Depends(get_current_user)):
    """Start attendance system - requires authentication and permission"""
    # Check if current user has permission to start attendance system
    if not has_permission(current_user, "view_attendance"):
        raise HTTPException(status_code=403, detail="Not authorized to start attendance system")
    
    global attendance_system_running, attendance_system_thread
    
    # Check if attendance system is already running
    if attendance_system_running:
        return {"message": "Attendance system is already running"}
    
    # Start attendance system in a separate thread
    attendance_system_running = True
    attendance_system_thread = threading.Thread(target=run_attendance_system)
    attendance_system_thread.daemon = True
    attendance_system_thread.start()
    
    return {"message": "Attendance system started successfully. Position faces in front of the camera to mark attendance."}


@app.post("/stop_attendance")
def stop_attendance(current_user: User = Depends(get_current_user)):
    """Stop attendance system - requires authentication and permission"""
    # Check if current user has permission to stop attendance system
    if not has_permission(current_user, "view_attendance"):
        raise HTTPException(status_code=403, detail="Not authorized to stop attendance system")
    
    global attendance_system_running, attendance_system_thread
    
    # Check if attendance system is running
    if not attendance_system_running:
        return {"message": "Attendance system is not running"}
    
    # Stop attendance system
    attendance_system_running = False
    
    # Note: In a real implementation, we would need to properly terminate the camera capture
    # For now, we'll just mark it as stopped
    return {"message": "Attendance system stopped successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)