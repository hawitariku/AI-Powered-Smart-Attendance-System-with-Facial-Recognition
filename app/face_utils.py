import torch
import numpy as np
import cv2
from facenet_pytorch import InceptionResnetV1, MTCNN


# Load Haar cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
mtcnn = MTCNN(image_size=160, margin=20)
model = InceptionResnetV1(pretrained='vggface2').eval()


def get_embedding(frame):
    # Convert to grayscale for face detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Detect faces using OpenCV
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    
    if len(faces) == 0:
        return None
    
    # Use the first detected face
    (x, y, w, h) = faces[0]
    
    # Extract face region
    face_region = frame[y:y+h, x:x+w]
    
    # Resize to the size expected by FaceNet
    face_region_resized = cv2.resize(face_region, (160, 160))
    
    # Convert BGR to RGB
    face_rgb = cv2.cvtColor(face_region_resized, cv2.COLOR_BGR2RGB)
    
    # Convert to tensor
    face_tensor = torch.tensor(face_rgb.transpose(2, 0, 1)).float()
    
    # Normalize
    face_tensor = (face_tensor - 127.5) / 128.0
    
    # Get embedding
    with torch.no_grad():
        emb = model(face_tensor.unsqueeze(0))
    
    return emb.numpy()[0]


def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))