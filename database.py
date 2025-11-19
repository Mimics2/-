from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import json

from config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class License(Base):
    __tablename__ = "licenses"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    owner_name = Column(String(200))
    email = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    requests_per_day = Column(Integer, default=settings.DEFAULT_REQUESTS_PER_DAY)
    total_requests = Column(Integer, default=0)
    
    requests = relationship("RequestLog", back_populates="license")

class RequestLog(Base):
    __tablename__ = "request_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id"))
    query = Column(String(500))
    results_count = Column(Integer)
    requested_at = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    
    license = relationship("License", back_populates="requests")

class ParsedData(Base):
    __tablename__ = "parsed_data"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("request_logs.id"))
    organization_id = Column(String(100))
    name = Column(String(500))
    categories = Column(Text)
    address = Column(Text)
    phones = Column(Text)
    website = Column(String(500))
    rating = Column(String(50))
    reviews_count = Column(Integer)
    schedule = Column(Text)
    latitude = Column(String(50))
    longitude = Column(String(50))
    attributes = Column(Text)
    social_networks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
