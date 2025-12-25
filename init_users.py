"""
Initialize users for the Smart Attendance System with RBAC
"""
from app.database import engine, Base, SessionLocal
from app.models import User
from app.auth import get_password_hash


def init_users():
    """
    Create initial users with different roles
    """
    print("Initializing users...")
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if admin user already exists
    admin_user = db.query(User).filter(User.email == "admin@attendance.com").first()
    
    if not admin_user:
        # Create admin user
        admin = User(
            name="Admin User",
            email="admin@attendance.com",
            password_hash=get_password_hash("admin123"),
            role="admin"
        )
        db.add(admin)
        print("Created admin user: admin@attendance.com / admin123")
    
    # Check if teacher user already exists
    teacher_user = db.query(User).filter(User.email == "teacher@attendance.com").first()
    
    if not teacher_user:
        # Create teacher user
        teacher = User(
            name="Teacher User",
            email="teacher@attendance.com",
            password_hash=get_password_hash("teacher123"),
            role="teacher"
        )
        db.add(teacher)
        print("Created teacher user: teacher@attendance.com / teacher123")
    
    # Check if regular user already exists
    regular_user = db.query(User).filter(User.email == "user@attendance.com").first()
    
    if not regular_user:
        # Create regular user
        user = User(
            name="Regular User",
            email="user@attendance.com",
            password_hash=get_password_hash("user123"),
            role="user"
        )
        db.add(user)
        print("Created regular user: user@attendance.com / user123")
    
    db.commit()
    db.close()
    print("Users initialized successfully!")


if __name__ == "__main__":
    init_users()