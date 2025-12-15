"""
Validate .env file database configuration
Helps identify configuration issues
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse, quote_plus

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print("⚠️  .env file not found. Looking in current directory...")
    load_dotenv()

def validate_database_config():
    """Validate database configuration"""
    print("🔍 Validating Database Configuration")
    print("=" * 50)
    print()
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print("✅ DATABASE_URL is set")
        print(f"   Value: {database_url[:50]}..." if len(database_url) > 50 else f"   Value: {database_url}")
        
        # Validate format
        if not (database_url.startswith("mysql://") or database_url.startswith("mysql+pymysql://")):
            print("   ⚠️  Warning: DATABASE_URL should start with 'mysql+pymysql://'")
        else:
            try:
                parsed = urlparse(database_url)
                print(f"   Host: {parsed.hostname or 'N/A'}")
                print(f"   Port: {parsed.port or 'N/A'}")
                print(f"   User: {parsed.username or 'N/A'}")
                print(f"   Database: {parsed.path.lstrip('/') or 'N/A'}")
                print(f"   Has Password: {'Yes' if parsed.password else 'No'}")
            except Exception as e:
                print(f"   ❌ Error parsing DATABASE_URL: {e}")
    else:
        print("ℹ️  DATABASE_URL not set, checking individual components...")
        print()
        
        # Check individual components
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "3306")
        db_user = os.getenv("DB_USER", "root")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "appointments_db")
        
        print(f"DB_HOST: {db_host}")
        print(f"DB_PORT: {db_port}")
        print(f"DB_USER: {db_user}")
        print(f"DB_PASSWORD: {'***' if db_password else '❌ NOT SET'}")
        print(f"DB_NAME: {db_name}")
        print()
        
        if not db_password:
            print("❌ DB_PASSWORD is not set!")
            print("   This will cause authentication failures.")
            print()
            print("Solution:")
            print("   Set DB_PASSWORD in your .env file:")
            print("   DB_PASSWORD=your_secure_password")
            return False
        
        # Build connection string
        encoded_password = quote_plus(db_password)
        database_url = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        print(f"✅ Would use connection string:")
        print(f"   mysql+pymysql://{db_user}:***@{db_host}:{db_port}/{db_name}")
    
    print()
    print("=" * 50)
    
    # Test connection
    print()
    print("🔍 Testing Connection...")
    try:
        from sqlalchemy import create_engine, text
        
        engine = create_engine(database_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"✅ Connection successful!")
            print(f"   MySQL: {version[:60]}...")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print()
        print("Common issues:")
        print("1. Wrong password - check DB_PASSWORD in .env")
        print("2. User doesn't exist - create user in MySQL")
        print("3. Database doesn't exist - create database")
        print("4. MySQL not running - start MySQL service: sudo service mysql start")
        print("5. Special characters in password - use URL encoding")
        return False

if __name__ == "__main__":
    success = validate_database_config()
    sys.exit(0 if success else 1)

