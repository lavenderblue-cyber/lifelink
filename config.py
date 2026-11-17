import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-development-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://lifelink:lifelink_dev_password@localhost:5432/lifelink"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
