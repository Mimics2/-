from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

from database import get_db, License, RequestLog, ParsedData, init_db
from auth import verify_license, create_license_key
from parser import YandexMapsParser
from config import settings

app = FastAPI(title="Yandex Maps Parser", version="1.0.0")

# Инициализация базы данных
init_db()

# Статические файлы и шаблоны
if not os.path.exists("static"):
    os.makedirs("static")
if not os.path.exists("templates"):
    os.makedirs("templates")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Глобальные переменные
parser_instance = None

def get_parser():
    global parser_instance
    if parser_instance is None:
        parser_instance = YandexMapsParser(headless=True)
    return parser_instance

@app.on_event("shutdown")
def shutdown_event():
    if parser_instance:
        parser_instance.close()

# API Endpoints
@app.post("/api/search")
async def search_organizations(
    request: Request,
    query: str = Form(...),
    city: str = Form(""),
    limit: int = Form(50),
    db: Session = Depends(get_db)
):
    """Поиск организаций"""
    
    # Проверка лицензии
    license_key = request.headers.get("X-License-Key")
    if not license_key:
        raise HTTPException(status_code=401, detail="Лицензионный ключ обязателен")
    
    license = verify_license(db, license_key)
    
    # Логирование запроса
    request_log = RequestLog(
        license_id=license.id,
        query=query,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    db.add(request_log)
    db.flush()
    
    # Поиск организаций
    parser = get_parser()
    try:
        organizations = parser.search_organizations(query, city, min(limit, 100))
        
        # Сохранение результатов
        for org in organizations:
            parsed_data = ParsedData(
                request_id=request_log.id,
                organization_id=org.get('id'),
                name=org.get('name', ''),
                categories=org.get('categories', ''),
                address=org.get('address', ''),
                phones=org.get('phones', ''),
                website=org.get('website', ''),
                rating=org.get('rating', ''),
                reviews_count=int(org.get('reviews_count', 0)) if org.get('reviews_count', '0').isdigit() else 0,
                schedule=org.get('schedule', ''),
                latitude=org.get('latitude', ''),
                longitude=org.get('longitude', ''),
                attributes=json.dumps(org.get('attributes', {})),
                social_networks=json.dumps(org.get('social_networks', {}))
            )
            db.add(parsed_data)
        
        request_log.results_count = len(organizations)
        license.total_requests += 1
        db.commit()
        
        return {
            "success": True,
            "count": len(organizations),
            "data": organizations,
            "remaining_requests": license.requests_per_day - db.query(RequestLog).filter(
                RequestLog.license_id == license.id,
                RequestLog.requested_at >= datetime.utcnow().date()
            ).count()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при парсинге: {str(e)}")

@app.get("/api/export/{request_id}")
async def export_results(
    request_id: int,
    format: str = "json",
    db: Session = Depends(get_db)
):
    """Экспорт результатов в разных форматах"""
    
    license_key = request.headers.get("X-License-Key")
    if not license_key:
        raise HTTPException(status_code=401, detail="Лицензионный ключ обязателен")
    
    license = verify_license(db, license_key)
    
    # Получение данных
    data = db.query(ParsedData).filter(ParsedData.request_id == request_id).all()
    
    if not data:
        raise HTTPException(status_code=404, detail="Данные не найдены")
    
    # Преобразование в DataFrame
    records = []
    for item in data:
        record = {
            'ID': item.organization_id,
            'Название': item.name,
            'Категории': item.categories,
            'Адрес': item.address,
            'Телефоны': item.phones,
            'Сайт': item.website,
            'Рейтинг': item.rating,
            'Отзывов': item.reviews_count,
            'График': item.schedule,
            'Широта': item.latitude,
            'Долгота': item.longitude
        }
        records.append(record)
    
    df = pd.DataFrame(records)
    
    if format == "csv":
        filename = f"results_{request_id}.csv"
        df.to_csv(f"static/{filename}", index=False, encoding='utf-8-sig')
        return FileResponse(f"static/{filename}", filename=filename)
    
    elif format == "excel":
        filename = f"results_{request_id}.xlsx"
        df.to_excel(f"static/{filename}", index=False)
        return FileResponse(f"static/{filename}", filename=filename)
    
    else:
        return JSONResponse(content=records)

# Admin endpoints
@app.post("/api/admin/licenses")
async def create_license(
    owner_name: str = Form(...),
    email: str = Form(...),
    duration_days: int = Form(30),
    requests_per_day: int = Form(100),
    db: Session = Depends(get_db)
):
    """Создание новой лицензии (только для админа)"""
    
    license_key = create_license_key()
    expires_at = datetime.utcnow() + timedelta(days=duration_days)
    
    license = License(
        key=license_key,
        owner_name=owner_name,
        email=email,
        expires_at=expires_at,
        requests_per_day=requests_per_day
    )
    
    db.add(license)
    db.commit()
    
    return {
        "success": True,
        "license_key": license_key,
        "expires_at": expires_at,
        "requests_per_day": requests_per_day
    }

@app.get("/api/admin/licenses")
async def get_licenses(db: Session = Depends(get_db)):
    """Получение списка всех лицензий"""
    licenses = db.query(License).all()
    
    result = []
    for license in licenses:
        today_requests = db.query(RequestLog).filter(
            RequestLog.license_id == license.id,
            RequestLog.requested_at >= datetime.utcnow().date()
        ).count()
        
        result.append({
            "id": license.id,
            "key": license.key,
            "owner_name": license.owner_name,
            "email": license.email,
            "is_active": license.is_active,
            "created_at": license.created_at,
            "expires_at": license.expires_at,
            "requests_per_day": license.requests_per_day,
            "today_requests": today_requests,
            "total_requests": license.total_requests
        })
    
    return result

# Web interface
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin")
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
