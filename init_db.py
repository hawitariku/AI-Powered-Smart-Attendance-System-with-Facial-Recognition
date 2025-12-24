"""
Initialize the database for the Smart Attendance System
"""
from app.database import engine, Base
from app.models import User, FaceEmbedding, Attendance

def init_db():
    """
    Create all database tables
    """
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")
    print("Tables created:")
    print("- users: For storing user information")
    print("- embeddings: For storing face embeddings")
    print("- attendance: For storing attendance records")

if __name__ == "__main__":
    init_db()