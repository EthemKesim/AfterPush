
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://afterpush:afterpush_local_dev@127.0.0.1:5432/afterpush",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
