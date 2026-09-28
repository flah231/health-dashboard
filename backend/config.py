from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "health_dashboard"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()