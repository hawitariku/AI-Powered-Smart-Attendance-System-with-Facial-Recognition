from sqlalchemy import Column, Integer, String, Date, Time, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, default="user")  # admin, teacher, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

class FaceEmbedding(Base):
    __tablename__ = "embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    embedding = Column(String)

class Attendance(Base):
    __tablename__ = "attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    date = Column(Date)
    time = Column(Time)
    status = Column(String)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String)  # admin, teacher, user
    permission = Column(String)  # register_user, enroll_face, view_attendance, etc.