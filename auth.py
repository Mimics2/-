from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
import secrets

from database import get_db, License
from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_license_key():
    return f"YKP-{datetime.now().strftime('%Y%m')}-{secrets.token_hex(4).upper()}"

def verify_license(db: Session, license_key: str):
    license = db.query(License).filter(License.key == license_key).first()
    
    if not license:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный лицензионный ключ"
        )
    
    if not license.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Лицензия неактивна"
        )
    
    if license.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия лицензии истек"
        )
    
    # Проверяем лимиты запросов за сегодня
    today = datetime.utcnow().date()
    today_requests = db.query(RequestLog).filter(
        RequestLog.license_id == license.id,
        RequestLog.requested_at >= today
    ).count()
    
    if today_requests >= license.requests_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен дневной лимит запросов"
        )
    
    return license

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
