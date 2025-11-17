# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Your Neon database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_pCUvIczyK2L9@ep-cool-frost-af45s6ic-pooler.c-2.us-west-2.aws.neon.tech/imposter_game?sslmode=require"
)

# Create the database engine
engine = create_engine(DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# Dependency to get a database session
def get_db():
    """
    Creates a new database session for each request.
    Automatically closes when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()