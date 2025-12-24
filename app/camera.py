import cv2
import numpy as np
from app.database import SessionLocal
from app.models import User, FaceEmbedding, Attendance
from app.face_utils import get_embedding, cosine_similarity
import datetime


def calculate_brightness(frame):
    """Calculate brightness of the frame"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)


def get_dynamic_threshold(frame):
    """Get dynamic threshold based on lighting conditions"""
    brightness = calculate_brightness(frame)
    
    if brightness > 180:  # Very bright
        return 0.70
    elif brightness > 120:  # Bright
        return 0.75
    elif brightness > 60:  # Normal
        return 0.80
    else:  # Dark
        return 0.85


def recognize_and_mark():
    # Initialize camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return
    
    print("Camera initialized. Starting face recognition...")
    
    # Load all embeddings from database
    db = SessionLocal()
    embeddings = db.query(FaceEmbedding).all()
    db.close()
    
    if not embeddings:
        print("No face embeddings found in database. Please enroll faces first.")
        return
    
    # Create a list of embeddings and corresponding user IDs
    known_embeddings = []
    user_ids = []
    for emb in embeddings:
        embedding_list = list(map(float, emb.embedding.split(',')))
        known_embeddings.append(np.array(embedding_list))
        user_ids.append(emb.user_id)
    
    print(f"Loaded {len(known_embeddings)} face embeddings for recognition")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Get embedding for current frame
        current_embedding = get_embedding(frame)
        
        if current_embedding is not None:
            # Get dynamic threshold based on lighting
            dynamic_threshold = get_dynamic_threshold(frame)
            
            # Compare with known embeddings
            best_match_idx = -1
            best_similarity = 0.0
            
            for i, known_emb in enumerate(known_embeddings):
                similarity = cosine_similarity(current_embedding, known_emb)
                if similarity > best_similarity and similarity > dynamic_threshold:  # Use dynamic threshold
                    best_similarity = similarity
                    best_match_idx = i
            
            if best_match_idx != -1:
                user_id = user_ids[best_match_idx]
                
                # Get user name
                db = SessionLocal()
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user_name = user.name
                    print(f"Recognized: {user_name} (ID: {user_id}) with similarity {best_similarity:.2f} (threshold: {dynamic_threshold:.2f})")
                    
                    # Check if attendance already marked today
                    today = datetime.date.today()
                    existing_attendance = db.query(Attendance).filter(
                        Attendance.user_id == user_id,
                        Attendance.date == today
                    ).first()
                    
                    if not existing_attendance:
                        # Mark attendance
                        record = Attendance(
                            user_id=user_id,
                            date=today,
                            time=datetime.datetime.now().time(),
                            status="Present"
                        )
                        db.add(record)
                        db.commit()
                        print(f"Attendance marked for {user_name}")
                    else:
                        print(f"Attendance already marked for {user_name} today")
                    
                db.close()
            else:
                # Face detected but not recognized
                print(f"Unknown face detected (similarity: {best_similarity:.2f}, threshold: {dynamic_threshold:.2f})")
        
        cv2.imshow("Attendance Camera", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        
        # Check if attendance system should stop
        import sys
        sys.path.append('.')
        try:
            from app.main import attendance_system_running
            if not attendance_system_running:
                break
        except ImportError:
            # If we can't import, continue running
            pass
    
    
    cap.release()
    cv2.destroyAllWindows()