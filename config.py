import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS = 30
    
    # Database
    DATABASE_URL = "sqlite:///./yandex_parser.db"
    
    # Parser settings
    MAX_RESULTS = 100
    REQUEST_DELAY = 2
    TIMEOUT = 30
    
    # License settings
    DEFAULT_REQUESTS_PER_DAY = 100
    LICENSE_DURATION_DAYS = 30

settings = Settings()
