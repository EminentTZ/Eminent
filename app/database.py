import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _default_database_url() -> str:
    db_dir = Path.cwd() / ".tmp" / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(db_dir / 'transport_system.db').as_posix()}"


DATABASE_URL = os.getenv("DATABASE_URL", _default_database_url())
# Render (and Heroku before it) hand out connection strings starting
# "postgres://", a scheme SQLAlchemy 2.x no longer accepts -- it wants
# "postgresql://". Rewriting it here means the same DATABASE_URL env var
# straight from the hosting provider just works, no manual editing needed.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# check_same_thread=False is an SQLite-only connect arg (it lets the one dev
# database file be shared across FastAPI's threadpool); passing it to any
# other DBAPI (e.g. psycopg2 for Postgres) raises a TypeError, so it's only
# included when the URL is actually SQLite.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
