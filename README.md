# Smart Attendance System

A complete face recognition-based attendance system using Python, FastAPI, OpenCV, and FaceNet.

## 🚀 Features

- **Face Recognition**: Uses FaceNet for accurate face recognition
- **Web Interface**: Complete web-based UI for all operations
- **Real-time Attendance**: Continuous monitoring with automatic attendance marking
- **Database Storage**: SQLite database for storing user data and attendance records
- **Automatic Attendance**: Attendance automatically marked when face is enrolled
- **Dynamic Threshold**: Adaptive recognition threshold based on lighting conditions
- **Multiple Sample Enrollment**: Improved accuracy by capturing multiple face samples during enrollment
- **Image Preprocessing**: Enhanced image quality for better recognition

## 📋 Prerequisites

- Python 3.8 or higher
- Camera device (webcam/laptop camera)
- Windows, macOS, or Linux

## 🔧 Installation

1. **Clone or create the project directory**
2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the database**:
   ```bash
   python init_db.py
   ```
   Or simply start the application - the database will be created automatically.

## ▶️ Starting the System

1. **Start the web server**:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
   ```

2. **Access the system**:
   Open your browser and go to: http://127.0.0.1:8002

## 🌐 Using the System

### Main Page Functions:

1. **Register New User**:
   - Enter user name in the text field
   - Click "Register User"
   - Note the User ID for enrollment

2. **Enroll Face**:
   - Enter the User ID from registration
   - Click "Enroll Face"
   - Position your face in front of the camera
   - System automatically marks attendance upon successful enrollment
   - Multiple face samples are captured for improved accuracy

3. **Start Real-time Attendance**:
   - Click "Start Real-time Attendance" to begin continuous monitoring
   - System runs in background, marking attendance when faces are detected
   - Uses dynamic threshold adjustment based on lighting conditions
   - Click "Stop Attendance System" to end monitoring

4. **View Attendance Records**:
   - Click "Go to Dashboard" to see all attendance records
   - Shows both registered users and attendance history

### Dashboard:

- **Registered Users**: Shows all registered users with their IDs and names
- **Attendance Records**: Shows all attendance records with date, time, and status

## 🔄 Complete Workflow

### Initial Setup:
1. Start the web server
2. Access http://127.0.0.1:8002 in your browser
3. Register all users who need attendance tracking
4. Enroll faces for each user (attendance automatically marked)

### Daily Usage:
1. Start the real-time attendance system
2. Users position themselves in front of the camera
3. System automatically marks attendance
4. Stop the attendance system when finished
5. Review attendance records in the dashboard

## 🛠️ Improvements Implemented

### 1. Dynamic Threshold Adjustment
- Recognition threshold adjusts based on lighting conditions
- Bright lighting: Lower threshold (0.70) for better sensitivity
- Normal lighting: Standard threshold (0.80)
- Dark lighting: Higher threshold (0.85) to prevent false matches

### 2. Multiple Sample Enrollment
- Captures up to 3 face samples during enrollment
- Uses average of embeddings for more robust recognition
- Better handles variations in pose and expression

### 3. Image Preprocessing
- Histogram equalization for better contrast
- Gaussian blur to reduce noise
- Enhanced image quality for improved recognition

### 4. Enhanced Feedback
- Real-time threshold information during recognition
- Clear indication of unknown faces
- Detailed logging of recognition process

## 📁 Project Structure

```
Attend/
├── app/
│   ├── main.py          # Main FastAPI application
│   ├── models.py        # Database models
│   ├── database.py      # Database configuration
│   ├── face_utils.py    # Face recognition utilities
│   └── camera.py        # Camera and attendance logic
├── templates/
│   ├── index.html       # Main interface
│   └── dashboard.html   # Dashboard interface
├── requirements.txt     # Python dependencies
├── init_db.py          # Database initialization script
├── README.md           # This file
└── USAGE_GUIDE.md      # Detailed user guide
```

## 🛠️ Troubleshooting

### Camera Issues:
- Ensure camera is properly connected
- Check that no other application is using the camera
- Try different lighting conditions
- Clean the camera lens

### Face Recognition Problems:
- Ensure face is well-lit and clearly visible
- Remove sunglasses or face coverings
- Position face squarely in front of camera
- Maintain consistent distance from camera

### Web Interface Issues:
- Refresh the page if elements don't load properly
- Clear browser cache if problems persist
- Ensure JavaScript is enabled in browser

### Server Issues:
- Check that the server is running (command prompt should show "Application startup complete")
- Verify port 8002 is not being used by another application
- Restart the server if it becomes unresponsive

## 📊 System Capabilities

### What the System Does:
- ✅ Registers users through web interface
- ✅ Enrolls faces with automatic attendance marking
- ✅ Provides real-time attendance tracking
- ✅ Shows attendance records in dashboard
- ✅ Works entirely through web browser (no terminal needed)
- ✅ Uses adaptive recognition for improved accuracy

### Technical Features:
- Real-time face detection using OpenCV
- Face recognition using FaceNet neural network
- SQLite database for persistent storage
- Responsive web interface
- Background processing for real-time monitoring
- Dynamic threshold adjustment for lighting conditions
- Multiple sample enrollment for better accuracy

## 🔒 Privacy and Security

### Data Storage:
- Face images are never stored
- Only mathematical representations (embeddings) are saved
- User names and attendance records stored locally
- No cloud transmission of personal data

### Data Protection:
- Database files stored locally on your device
- No external access to attendance data
- Easy backup and migration of database files

## 🆘 Need Help?

If you encounter any issues not covered in this guide:
1. Check the server console for error messages
2. Verify all prerequisites are installed
3. Restart the server and try again
4. Contact technical support with detailed error information