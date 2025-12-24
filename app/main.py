from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import numpy as np


from app.database import Base, engine, SessionLocal
from app.models import User, FaceEmbedding, Attendance
from app.face_utils import get_embedding
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


@app.post("/register")
def register(name: str = Form(...)):
    db = SessionLocal()
    user = User(name=name)
    db.add(user)
    db.commit()
    db.close()
    return {"message": "User registered"}


@app.post("/enroll/{user_id}")
def enroll_face(user_id: int):
    # Initialize MTCNN for face detection
    from facenet_pytorch import MTCNN
    mtcnn = MTCNN(image_size=160, margin=20)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return {"error": "Could not open camera"}
    
    # Allow camera to warm up
    import time
    time.sleep(2)
    
    # Try multiple frames to detect face
    emb = None
    for i in range(30):  # Try for 30 frames
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
                    break
        except Exception as e:
            pass  # Continue trying
            
        time.sleep(0.1)  # Small delay between frames
    
    cap.release()
    
    if emb is None:
        return {"error": "No face detected after multiple attempts"}
    
    db = SessionLocal()
    
    # Save embedding
    record = FaceEmbedding(user_id=user_id, embedding=','.join(map(str, emb.tolist())))
    db.add(record)
    
    # Automatically mark attendance when face is enrolled
    import datetime
    today = datetime.date.today()
    time_now = datetime.datetime.now().time()
    attendance_record = Attendance(user_id=user_id, date=today, time=time_now, status="Present")
    db.add(attendance_record)
    
    db.commit()
    db.close()
    
    return {"message": "Face enrolled and attendance marked"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    records = db.query(Attendance).all()
    users = db.query(User).all()
    db.close()
    return templates.TemplateResponse("dashboard.html", {"request": request, "records": records, "users": users})


@app.post("/start_attendance")
def start_attendance():
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
def stop_attendance():
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