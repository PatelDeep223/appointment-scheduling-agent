"""
Database configuration and session management
Configured for MySQL (can fallback to SQLite for development)
"""

import os
from pathlib import Path
from urllib.parse import urlparse, quote_plus, unquote
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

# Load environment variables from .env file
# Try multiple paths to find .env file (project root or backend/)
env_paths = [
    Path(__file__).parent.parent / ".env",  # Project root
    Path(__file__).parent / ".env",        # Backend directory
    Path(".env"),                           # Current directory
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        env_loaded = True
        print(f"✅ Loaded .env from: {env_path}")
        break

if not env_loaded:
    # Fallback: try loading from current directory
    load_dotenv(override=True)
    print("⚠️  Using default .env loading (may not find correct file)")

# Ensure data directory exists (for SQLite fallback)
data_dir = Path("./data")
data_dir.mkdir(exist_ok=True)

# Database URL - MySQL by default, SQLite as fallback
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    None  # Will use MySQL connection string if not set
)

# If DATABASE_URL not set, try to build from individual components
if not DATABASE_URL:
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "appointments_db")
    
    # Debug: Print what we're using
    print(f"🔍 Database Configuration:")
    print(f"   Host: {db_host}")
    print(f"   Port: {db_port}")
    print(f"   User: {db_user}")
    print(f"   Database: {db_name}")
    print(f"   Password: {'<set>' if db_password else '<not set>'}")
    
    if db_password:
        # URL encode password to handle special characters
        from urllib.parse import quote_plus
        encoded_password = quote_plus(db_password)
        # Use mysql+pymysql:// for PyMySQL driver
        DATABASE_URL = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    else:
        # Fallback to SQLite if no MySQL credentials
        DATABASE_URL = "sqlite:///./data/appointments.db"
        print("⚠️  No MySQL password found, using SQLite for development")
        print("   To use MySQL, set DB_PASSWORD in .env file")

# Try to connect to MySQL, fallback to SQLite if it fails
USE_SQLITE = False
if DATABASE_URL and (DATABASE_URL.startswith("mysql") or DATABASE_URL.startswith("mysql+pymysql")):
    try:
        # Test MySQL connection
        from sqlalchemy import text
        test_engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2}  # 2 second timeout
        )
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        test_engine.dispose()
        print(f"✅ MySQL connection successful")
    except Exception as e:
        print(f"⚠️  MySQL connection failed: {str(e)}")
        print("   Falling back to SQLite for demo mode")
        DATABASE_URL = "sqlite:///./data/appointments.db"
        USE_SQLITE = True

# Extract database info for logging (safely using urlparse)
db_info = "MySQL"
if DATABASE_URL and (DATABASE_URL.startswith("mysql") or DATABASE_URL.startswith("mysql+pymysql")):
    try:
        # Use urlparse for safe parsing (handles special characters correctly)
        parsed = urlparse(DATABASE_URL)
        log_host = parsed.hostname or "localhost"
        log_port = parsed.port or 3306
        log_db = parsed.path.lstrip("/").split("?")[0] if parsed.path else "unknown"
        log_user = unquote(parsed.username) if parsed.username else "unknown"
        
        db_info = f"{log_db}@{log_host}:{log_port}"
    except Exception as e:
        # If parsing fails, just use generic info
        db_info = "MySQL"
        print(f"⚠️  Could not parse database URL for logging: {e}")

# Create engine with appropriate configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("DEBUG", "False").lower() == "true",
        pool_pre_ping=True  # Verify connections before using
    )
    print("📦 Using SQLite database")
else:
    # MySQL configuration
    # Use connection pooling for better performance
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,  # Number of connections to maintain
        max_overflow=20,  # Additional connections if pool is exhausted
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=os.getenv("DEBUG", "False").lower() == "true"
    )
    print(f"🐬 Using MySQL database: {db_info}")

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Global flag to check if database connection is working
_db_connection_working = False

def check_db_connection() -> bool:
    """Check if database connection is working"""
    global _db_connection_working
    if _db_connection_working:
        return True
    
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_connection_working = True
        return True
    except Exception:
        _db_connection_working = False
        return False

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI
    
    Usage:
        @app.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    Call this on application startup
    Returns True if successful, False if failed (app can continue without DB)
    """
    try:
        # Import all models here so they're registered with Base
        # Try different import strategies based on how the module is being run
        Booking = None
        
        # Strategy 1: Direct import (when running from backend/ directory)
        try:
            from models.booking import Booking
        except ImportError:
            # Strategy 2: Relative import (when running as package)
            try:
                from .models.booking import Booking
            except ImportError:
                # Strategy 3: Absolute import (when running from project root)
                try:
                    from backend.models.booking import Booking
                except ImportError:
                    print("⚠️  Could not import Booking model - database features disabled")
                    return False
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Verify table was created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if "bookings" in tables:
            print("✅ Database initialized - 'bookings' table created")
            global _db_connection_working
            _db_connection_working = True
            return True
        else:
            print("⚠️  Database initialized but 'bookings' table not found")
            print(f"   Available tables: {tables}")
            _db_connection_working = True  # Connection works, just missing table
            return True
            
    except Exception as e:
        print(f"⚠️  Database initialization failed: {str(e)}")
        print("   Continuing in demo mode without database")
        import traceback
        traceback.print_exc()
        return False

