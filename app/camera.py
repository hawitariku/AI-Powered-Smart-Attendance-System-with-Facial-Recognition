import cv2
import numpy as np
import torch
import random
import math
from app.database import SessionLocal
from app.models import FaceEmbedding, Attendance, User
from app.face_utils import get_embedding
from app.auth import ENCRYPTION_KEY
from cryptography.fernet import Fernet
import datetime
import time
import os

def log_debug(message):
    """Helper to write debug logs to a file for web viewing"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    with open("debug_live.log", "a") as f:
        f.write(log_line)
    print(log_line.strip())

def dist(p1, p2):
    """Calculate Euclidean distance between two points"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def draw_text_with_bg(frame, text, x, y, color=(255, 255, 255), size=0.8, thickness=2, bg_color=(0, 0, 0)):
    """Ultra-robust text drawing with background and boundary checks"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    h, w, _ = frame.shape
    (tw, th), _ = cv2.getTextSize(text, font, size, thickness)
    x = max(10, min(x, w - tw - 10))
    y = max(th + 10, min(y, h - 10))
    cv2.rectangle(frame, (x-5, y - th - 10), (x + tw + 5, y + 10), bg_color, -1)
    cv2.putText(frame, text, (x, y), font, size, color, thickness, cv2.LINE_AA)

class RemoteFaceProcessor:
    """
    Stateful processor for remote (browser-based) liveness and recognition.
    Processes one frame at a time and returns instructions/status.
    """
    def __init__(self):
        # --- CONFIG (Consistent with recognize_and_mark) ---
        self.RECOGNITION_THRESHOLD = 0.55
        self.CONFLICT_THRESHOLD = 0.55
        self.STEP_TIMEOUT = 20.0
        self.TOTAL_STEPS = 1
        self.GRACE_PERIOD = 8.0
        
        self.STATE_SEARCHING = "SEARCHING"
        self.STATE_COLLECTING_BASELINE = "COLLECTING"
        self.STATE_CHALLENGE = "CHALLENGE"
        
        self.CH_SMILE, self.CH_NOD = "SMILE", "NOD"
        self.THRESHOLD_MAP = { self.CH_SMILE: 0.08, self.CH_NOD: 4.0 }
        
        # --- STATE ---
        self.current_state = self.STATE_SEARCHING
        self.baseline_buffer = []
        self.baseline_final = None
        self.nose_history = []
        self.challenge_sequence = []
        self.current_step_idx = 0
        self.state_start_time = time.time()
        self.last_face_time = time.time()
        
        # Load MTCNN once
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        from facenet_pytorch import MTCNN
        self.mtcnn = MTCNN(image_size=160, margin=20, keep_all=False, select_largest=True, device=device)
        self.cipher = Fernet(ENCRYPTION_KEY) if ENCRYPTION_KEY else None

    def process_frame(self, frame, user_id, mode="ATTEND"):
        """
        Processes a single frame.
        Returns: { 'instruction': str, 'status': str, 'progress': int, 'success': bool }
        """
        if not self.cipher:
            return {"instruction": "System Error: Missing Key", "status": "ERROR"}

        h, w, _ = frame.shape
        result = {"instruction": "Look at the camera", "status": self.current_state, "progress": 0, "success": False}

        try:
            # Fetch user name for logging
            db = SessionLocal()
            u_obj = db.query(User).filter(User.id == user_id).first()
            user_name = u_obj.name if u_obj else f"User {user_id}"
            db.close()

            boxes, probs, landmarks = self.mtcnn.detect(frame, landmarks=True)
            
            if boxes is not None:
                self.last_face_time = time.time()
                idx = 0 # MTCNN select_largest=True ensures one face
                box = boxes[0]
                
                # 1. SEARCHING
                if self.current_state == self.STATE_SEARCHING:
                    x1, y1, x2, y2 = [int(b) for b in box]
                    face_region = frame[y1:y2, x1:x2]
                    if face_region.size > 0:
                        emb = get_embedding(face_region)
                        if emb is not None:
                            db = SessionLocal()
                            stored = db.query(FaceEmbedding).all()
                            best_sim = 0
                            best_uid = None
                            for s in stored:
                                try:
                                    d = self.cipher.decrypt(s.embedding.encode()).decode()
                                    v = np.array([float(x) for x in d.split(',')])
                                    sim = np.dot(emb, v) / (np.linalg.norm(emb) * np.linalg.norm(v))
                                    if sim > best_sim:
                                        best_sim = sim
                                        best_uid = s.user_id
                                except: continue
                            db.close()

                            trigger = False
                            if mode == "ATTEND":
                                # For remote attendance, we MUST match the logged-in user
                                if best_uid == user_id and best_sim > self.RECOGNITION_THRESHOLD:
                                    trigger = True
                                elif best_sim > self.RECOGNITION_THRESHOLD:
                                    # Case: Another employee trying to use this account
                                    result["instruction"] = "🚫 ACCESS DENIED: Identity Mismatch detected!"
                                    log_debug(f"SECURITY ALERT: {user_name} account attempted by another employee (Matched ID: {best_uid})")
                                else:
                                    # Case: A stranger not in the system
                                    result["instruction"] = "🚫 ACCESS DENIED: Unknown Face detected!"
                                    log_debug(f"SECURITY ALERT: Unauthorized stranger detected on {user_name}'s account")
                            else: # ENROLL
                                if best_sim > self.CONFLICT_THRESHOLD and best_uid != user_id:
                                    result["instruction"] = "Identity already enrolled in another account"
                                    log_debug(f"Remote: Enrollment Conflict for {user_name}")
                                else:
                                    self.captured_embedding = emb
                                    trigger = True
                            
                            if trigger:
                                self.current_state = self.STATE_COLLECTING_BASELINE
                                self.state_start_time = time.time()
                                self.baseline_buffer = []
                                self.challenge_sequence = random.sample([self.CH_SMILE, self.CH_NOD], self.TOTAL_STEPS)
                                result["instruction"] = "Face recognized. Calibrating..."
                                log_debug(f"Remote: Starting Liveness Check for {user_name} ({mode})")

                # 2. COLLECTING
                elif self.current_state == self.STATE_COLLECTING_BASELINE:
                    result["instruction"] = "CALIBRATING... STAY STILL"
                    if landmarks is not None:
                        lm = landmarks[0]
                        ed = dist(lm[0], lm[1])
                        m_ratio = dist(lm[3], lm[4]) / ed
                        self.baseline_buffer.append({"mr": m_ratio, "ny": lm[2][1]})
                    
                        if len(self.baseline_buffer) >= 10:
                            self.baseline_final = {
                                "mr": np.mean([b["mr"] for b in self.baseline_buffer]),
                                "ny": np.mean([b["ny"] for b in self.baseline_buffer])
                            }
                            self.current_state = self.STATE_CHALLENGE
                            self.state_start_time = time.time()
                            curr_task = self.challenge_sequence[0]
                            result["instruction"] = f"Action: {curr_task}"
                            log_debug(f"Remote: Calibration complete for {user_name}. Challenge: {curr_task}")

                # 3. CHALLENGE
                elif self.current_state == self.STATE_CHALLENGE:
                    curr_task = self.challenge_sequence[self.current_step_idx]
                    result["instruction"] = f"PLEASE {curr_task}"
                    
                    if landmarks is not None:
                        lm = landmarks[0]
                        ed = dist(lm[0], lm[1])
                        m_ratio = dist(lm[3], lm[4]) / ed
                        ny_val = lm[2][1]
                        
                        is_passed = False
                        req = self.THRESHOLD_MAP[curr_task]
                        
                        if curr_task == self.CH_SMILE:
                            diff = m_ratio - self.baseline_final["mr"]
                            result["progress"] = min(100, int((diff / req) * 100))
                            if diff > req: is_passed = True
                        elif curr_task == self.CH_NOD:
                            self.nose_history.append(ny_val)
                            if len(self.nose_history) > 15: self.nose_history.pop(0)
                            diff = max(self.nose_history) - min(self.nose_history)
                            result["progress"] = min(100, int((diff / req) * 100))
                            if diff > req: is_passed = True

                        if is_passed:
                            result["success"] = True
                            result["instruction"] = "VERIFIED!"
                            db = SessionLocal()
                            if mode == "ATTEND":
                                today = datetime.date.today()
                                if not db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.date == today).first():
                                    db.add(Attendance(user_id=user_id, date=today, time=datetime.datetime.now().time(), status="Present (Remote)"))
                                    db.commit()
                                    log_debug(f"Remote: Auto-Marked Present: {user_name}")
                            else: # ENROLL
                                db.query(FaceEmbedding).filter(FaceEmbedding.user_id == user_id).delete()
                                eb_s = ",".join([str(x) for x in self.captured_embedding])
                                enc = self.cipher.encrypt(eb_s.encode()).decode()
                                db.add(FaceEmbedding(user_id=user_id, embedding=enc))
                                db.commit()
                                log_debug(f"Remote: NEW ENROLLMENT SUCCESS: {user_name}")
                            db.close()
                            # Reset for next time
                            self.current_state = self.STATE_SEARCHING

                if time.time() - self.state_start_time > self.STEP_TIMEOUT and self.current_state != self.STATE_SEARCHING:
                    log_debug(f"Remote: Liveness Timeout for {user_name} during {self.current_state}")
                    self.current_state = self.STATE_SEARCHING
                    result["instruction"] = "Timeout. Try again."

            else: # No face
                if self.current_state != self.STATE_SEARCHING:
                    if time.time() - self.last_face_time > self.GRACE_PERIOD:
                        self.current_state = self.STATE_SEARCHING
                        result["instruction"] = "Face lost. Restarting..."
                    else:
                        result["instruction"] = "FACE LOST! Return to frame."

        except Exception as e:
            print(f"Remote Processing Error: {e}")
            result["instruction"] = "Processing Error"
            self.current_state = self.STATE_SEARCHING

        result["status"] = self.current_state
        return result


def recognize_and_mark(enroll_user_id=None):
    """
    Classic/Admin Liveness System (centralized)
    V5: Remains for office desk use.
    """
    mode = "ENROLL" if enroll_user_id else "ATTEND"
    
    if os.path.exists("debug_live.log"):
        os.remove("debug_live.log")
        
    log_debug(f"Starting {mode} Liveness System (Ultra-Forgiving Mode)...")
    
    if not ENCRYPTION_KEY:
        log_debug("Error: ENCRYPTION_KEY missing")
        return
        
    cipher = Fernet(ENCRYPTION_KEY)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        log_debug("Error: Camera not found")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    from facenet_pytorch import MTCNN
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        mtcnn = MTCNN(image_size=160, margin=20, keep_all=False, select_largest=True, device=device)
    except:
        mtcnn = MTCNN(image_size=160, margin=20, keep_all=False, select_largest=True)
    
    # --- ULTRA-FORGIVING CONFIG ---
    RECOGNITION_THRESHOLD = 0.55
    CONFLICT_THRESHOLD = 0.55
    STEP_TIMEOUT = 20.0
    TOTAL_STEPS = 1 
    GRACE_PERIOD = 8.0 
    
    CH_SMILE, CH_NOD = "SMILE", "NOD"
    all_challenges = [CH_SMILE, CH_NOD]
    
    THRESHOLD_MAP = { CH_SMILE: 0.08, CH_NOD: 4.0 }
    
    STATE_SEARCHING = "SEARCHING"
    STATE_COLLECTING_BASELINE = "COLLECTING"
    STATE_CHALLENGE = "CHALLENGE"
    
    current_state = STATE_SEARCHING
    challenge_sequence = []
    current_step_idx = 0
    target_user_id = enroll_user_id
    target_user_name = ""
    captured_embedding = None
    
    state_start_time = 0
    baseline_buffer = []
    baseline_final = None
    nose_history = []
    last_face_time = time.time()
    frame_count = 0

    if mode == "ENROLL":
        db = SessionLocal()
        user = db.query(User).filter(User.id == target_user_id).first()
        target_user_name = user.name if user else "User"
        db.close()

    while True:
        ret, frame = cap.read()
        if not ret: break
        h, w, _ = frame.shape
        frame_count += 1
        
        draw_text_with_bg(frame, f"SECURE VERIFICATION: {mode}", 20, 40, (0, 255, 0), 0.6, 2)
        
        try:
            boxes, probs, landmarks = mtcnn.detect(frame, landmarks=True)
            if boxes is not None:
                last_face_time = time.time()
                for idx, box in enumerate(boxes):
                    x1, y1, x2, y2 = [int(b) for b in box]
                    
                    if current_state == STATE_SEARCHING:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        face_region = frame[y1:y2, x1:x2]
                        if face_region.size == 0: continue
                        emb = get_embedding(face_region)
                        if emb is None: continue
                        
                        db = SessionLocal()
                        stored = db.query(FaceEmbedding).all()
                        best_sim = 0
                        best_uid = None
                        for s in stored:
                            try:
                                d = cipher.decrypt(s.embedding.encode()).decode()
                                v = np.array([float(x) for x in d.split(',')])
                                sim = np.dot(emb, v) / (np.linalg.norm(emb) * np.linalg.norm(v))
                                if sim > best_sim:
                                    best_sim = sim
                                    best_uid = s.user_id
                            except: continue
                        db.close()

                        trigger = False
                        if mode == "ATTEND" and best_sim > RECOGNITION_THRESHOLD:
                            trigger = True; target_user_id = best_uid
                            db = SessionLocal()
                            u = db.query(User).filter(User.id == target_user_id).first()
                            target_user_name = u.name if u else "User"
                            db.close()
                        elif mode == "ENROLL":
                            if best_sim > CONFLICT_THRESHOLD and best_uid != enroll_user_id:
                                log_debug(f"Identity Already Enrolled as User {best_uid}")
                                draw_text_with_bg(frame, "IDENTITY CONFLICT DETECTED", x1, y1-10, (255, 255, 255), 0.7, 2, (0,0,255))
                                cv2.imshow('Liveness System', frame); cv2.waitKey(2000)
                                cap.release(); cv2.destroyAllWindows(); return
                            trigger = True; captured_embedding = emb
                        
                        if trigger:
                            current_state = STATE_COLLECTING_BASELINE
                            state_start_time = time.time()
                            baseline_buffer = []
                            challenge_sequence = random.sample(all_challenges, TOTAL_STEPS) 
                            current_step_idx = 0
                            log_debug(f"Face recognized. Calibrating sensors for {target_user_name}...")

                    elif current_state == STATE_COLLECTING_BASELINE:
                        instr = "CALIBRATING... STAY STILL"
                        draw_text_with_bg(frame, instr, w//2 - 150, 80, (255, 255, 0), 0.8, 2)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 3)
                        if landmarks is not None and len(landmarks) > idx:
                            lm = landmarks[idx]
                            m_ratio = dist(lm[3], lm[4]) / dist(lm[0], lm[1])
                            baseline_buffer.append({"mr": m_ratio, "ny": lm[2][1]})
                        if len(baseline_buffer) >= 12:
                            baseline_final = {"mr": np.mean([b["mr"] for b in baseline_buffer]), "ny": np.mean([b["ny"] for b in baseline_buffer])}
                            current_state = STATE_CHALLENGE; state_start_time = time.time()
                            log_debug(f"Calibration Complete. Challenge: {challenge_sequence[current_step_idx]}")

                    elif current_state == STATE_CHALLENGE:
                        curr_task = challenge_sequence[current_step_idx]
                        draw_text_with_bg(frame, f"PLEASE {curr_task}", w//2 - 120, 80, (0, 255, 255), 0.9, 2)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 4)
                        timeLeft = int(STEP_TIMEOUT - (time.time() - state_start_time))
                        draw_text_with_bg(frame, f"TIME: {timeLeft}s", x1, y2 + 25, (255,255,255), 0.5, 1)

                        if landmarks is not None and len(landmarks) > idx:
                            lm = landmarks[idx]
                            m_ratio = dist(lm[3], lm[4]) / dist(lm[0], lm[1]); ny_val = lm[2][1]
                            is_passed = False; prog = 0; req = THRESHOLD_MAP[curr_task]
                            if curr_task == CH_SMILE:
                                diff = m_ratio - baseline_final["mr"]
                                prog = min(100, int((diff / req) * 100))
                                if diff > req: is_passed = True
                            elif curr_task == CH_NOD:
                                nose_history.append(ny_val)
                                if len(nose_history) > 15: nose_history.pop(0)
                                diff = max(nose_history) - min(nose_history)
                                prog = min(100, int((diff / req) * 100))
                                if diff > req: is_passed = True

                            bw = x2 - x1
                            cv2.rectangle(frame, (x1, y2+45), (x1 + int(bw * prog/100), y2+60), (0, 255, 0), -1)
                            cv2.rectangle(frame, (x1, y2+45), (x2, y2+60), (255, 255, 255), 2)
                            if frame_count % 60 == 0: log_debug(f"Action: {curr_task} | Progress: {prog}%")

                            if is_passed:
                                log_debug("Challenge PASSED!")
                                db = SessionLocal()
                                if mode == "ATTEND":
                                    today = datetime.date.today()
                                    if not db.query(Attendance).filter(Attendance.user_id == target_user_id, Attendance.date == today).first():
                                        db.add(Attendance(user_id=target_user_id, date=today, time=datetime.datetime.now().time(), status="Present")); db.commit()
                                else:
                                    db.query(FaceEmbedding).filter(FaceEmbedding.user_id == target_user_id).delete()
                                    enc = cipher.encrypt(",".join([str(x) for x in captured_embedding]).encode()).decode()
                                    db.add(FaceEmbedding(user_id=target_user_id, embedding=enc)); db.commit()
                                db.close()
                                draw_text_with_bg(frame, "VERIFIED - SUCCESS", x1, y2+100, (0,255,0), 0.9, 2)
                                cv2.imshow('Liveness System', frame); cv2.waitKey(2000)
                                if mode == "ENROLL": cap.release(); cv2.destroyAllWindows(); return
                                current_state = STATE_SEARCHING; nose_history = []

                        if time.time() - state_start_time > STEP_TIMEOUT:
                            log_debug("Challenge Timeout. Please try again.")
                            current_state = STATE_SEARCHING
            else:
                if current_state != STATE_SEARCHING:
                    if time.time() - last_face_time > GRACE_PERIOD:
                        log_debug("Face detection lost. Sequence Reset."); current_state = STATE_SEARCHING
                    else:
                        draw_text_with_bg(frame, "FACE LOST! STAY IN FRAME", 20, 100, (0, 0, 255), 0.7, 2)
            cv2.imshow('Liveness System', frame)
        except Exception as e:
            log_debug(f"Error: {e}"); current_state = STATE_SEARCHING
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release(); cv2.destroyAllWindows()

if __name__ == "__main__":
    recognize_and_mark()