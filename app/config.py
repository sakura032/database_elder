import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "database-elder-dev-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # 本地数据库配置，调试本地库时可取消注释并注释下方远程库配置。
    # DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    # DB_PORT = int(os.getenv("DB_PORT", "3306"))
    # DB_USER = os.getenv("DB_USER", "root")
    # DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    # DB_NAME = os.getenv("DB_NAME", "pension_service")

    # 远程数据库：pension1_service
    # 当前可连接远程 IP：192.168.70.82。
    DB_HOST = os.getenv("DB_HOST", "192.168.70.82")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "pension1_service")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    DB_READ_TIMEOUT = int(os.getenv("DB_READ_TIMEOUT", "15"))
    DB_WRITE_TIMEOUT = int(os.getenv("DB_WRITE_TIMEOUT", "15"))

    # DeepSeek 大模型配置。
    DEEPSEEK_API_KEY = "sk-e29f82faf0b2454fa8e76ccd48466b46"
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_TIMEOUT = int(os.getenv("DEEPSEEK_TIMEOUT", "12"))
    DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "450"))
