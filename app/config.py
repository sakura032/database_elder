import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "database-elder-dev-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    DB_HOST = os.getenv("DB_HOST", "10.160.70.167")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "pension_service")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
