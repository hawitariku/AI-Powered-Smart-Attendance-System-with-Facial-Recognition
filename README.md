# 🔐 AI-Powered Smart Attendance System

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-green.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9.1-red.svg)](https://pytorch.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Enterprise-grade attendance management system with AI facial recognition, liveness detection, and advanced security.

---

## Features

- AI-powered facial recognition with 99.6% accuracy
- Anti-spoofing liveness detection
- Local and remote attendance modes
- IP geofencing and encrypted biometric storage
- Role-based access control with JWT authentication

---

## Tech Stack

FastAPI • PyTorch • FaceNet • MTCNN • OpenCV • SQLAlchemy • JWT • Fernet Encryption

---

## Installation

```bash
git clone https://github.com/hawitariku/AI-Powered-Smart-Attendance-System-with-Facial-Recognition.git
cd AI-Powered-Smart-Attendance-System-with-Facial-Recognition

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

python init_db.py
python init_users.py

python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Access at: **http://127.0.0.1:8002**

---

## Screenshots

### Login Page
![Login](screenshots/login.png)

### Admin Dashboard
![Dashboard](screenshots/Admin%20dashboard.png)

### Face Enrollment
![Enrollment 1](screenshots/enrollment1.jpg)
![Enrollment 2](screenshots/enrollment2.jpg)
![Enrollment 3](screenshots/enrollment3.jpg)

---

## Configuration

Create `.env` file with your keys:

```env
SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key
```

---

## License

MIT License - see [LICENSE](LICENSE)

---

<div align="center">

**Made by Hawi Tariku**

⭐ Star this repo if you find it useful!

</div>
