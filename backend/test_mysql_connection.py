#!/usr/bin/env python3
"""
MySQL Connection Test Script
Tests MySQL database connection and configuration
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv

# Try multiple paths to find .env file
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
    load_dotenv(override=True)
    print("⚠️  Using default .env loading")

from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus


def test_mysql_connection():
    """Test MySQL database connection"""
    
    print("\n" + "="*60)
    print("MySQL Connection Test")
    print("="*60 + "\n")
    
    # Get database configuration
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "appointments_db")
    
    # Warn if using PostgreSQL port
    if db_port == "5432":
        print("⚠️  WARNING: DB_PORT is set to 5432 (PostgreSQL port)")
        print("   MySQL uses port 3306. Update your .env file:")
        print("   DB_PORT=3306")
        print()
    
    # Check if DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        print(f"📋 Using DATABASE_URL from environment")
        if not database_url.startswith("mysql"):
            print(f"⚠️  Warning: DATABASE_URL doesn't start with 'mysql'")
            print(f"   Current: {database_url[:20]}...")
            print(f"   Expected format: mysql+pymysql://user:password@host:3306/database?charset=utf8mb4")
    else:
        print(f"📋 Building connection string from individual components:")
        print(f"   Host: {db_host}")
        print(f"   Port: {db_port}")
        print(f"   User: {db_user}")
        print(f"   Database: {db_name}")
        print(f"   Password: {'<set>' if db_password else '<not set>'}")
        
        if db_password:
            encoded_password = quote_plus(db_password)
            database_url = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        else:
            database_url = f"mysql+pymysql://{db_user}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    
    print(f"\n🔌 Attempting to connect to MySQL...")
    
    try:
        # Create engine
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5}
        )
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            
            if test_value == 1:
                print("✅ MySQL connection successful!")
            else:
                print(f"⚠️  Connection test returned unexpected value: {test_value}")
        
        # Test database exists
        print("\n🔍 Checking database...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DATABASE()"))
            current_db = result.fetchone()[0]
            
            if current_db == db_name:
                print(f"✅ Connected to database '{db_name}'")
            else:
                print(f"⚠️  Connected to database '{current_db}' (expected '{db_name}')")
        
        # Check if database exists
        with engine.connect() as conn:
            result = conn.execute(text("SHOW DATABASES"))
            databases = [row[0] for row in result.fetchall()]
            
            if db_name in databases:
                print(f"✅ Database '{db_name}' exists")
            else:
                print(f"❌ Database '{db_name}' does not exist")
                print(f"   Available databases: {', '.join(databases)}")
                print(f"\n   To create the database, run:")
                print(f"   mysql -u {db_user} -p -e \"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\"")
                return False
        
        # Test user permissions
        print("\n🔍 Checking user permissions...")
        with engine.connect() as conn:
            result = conn.execute(text(f"SHOW GRANTS FOR '{db_user}'@'%'"))
            grants = [row[0] for row in result.fetchall()]
            
            if not grants:
                # Try localhost
                result = conn.execute(text(f"SHOW GRANTS FOR '{db_user}'@'localhost'"))
                grants = [row[0] for row in result.fetchall()]
            
            if grants:
                print(f"✅ User '{db_user}' has permissions")
                print(f"   Grants: {len(grants)} permission(s)")
            else:
                print(f"⚠️  Could not verify permissions for user '{db_user}'")
        
        # Test table creation (if database exists)
        print("\n🔍 Testing table operations...")
        with engine.connect() as conn:
            # Check if bookings table exists
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if "bookings" in tables:
                print(f"✅ Table 'bookings' exists")
                
                # Get table info
                columns = inspector.get_columns("bookings")
                print(f"   Columns: {len(columns)}")
                print(f"   Column names: {', '.join([col['name'] for col in columns[:5]])}...")
            else:
                print(f"ℹ️  Table 'bookings' does not exist (will be created on first run)")
        
        # Test a simple query
        print("\n🔍 Testing query execution...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION() as version, NOW() as current_time"))
            row = result.fetchone()
            version = row[0]
            current_time = row[1]
            
            print(f"✅ Test query executed successfully")
            print(f"   MySQL Version: {version}")
            print(f"   Current Time: {current_time}")
        
        print("\n" + "="*60)
        print("✅ All tests passed! MySQL is ready to use.")
        print("="*60 + "\n")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("   Make sure you've installed the required packages:")
        print("   pip install pymysql sqlalchemy python-dotenv")
        return False
        
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\n🔧 Troubleshooting steps:")
        print("   1. Check if MySQL service is running:")
        print("      sudo service mysql status")
        print("   2. Verify database credentials in .env file")
        print("   3. Check if database exists:")
        print(f"      mysql -u {db_user} -p -e 'SHOW DATABASES;'")
        print("   4. Verify user has proper permissions")
        print("   5. Check MySQL error logs:")
        print("      sudo tail -f /var/log/mysql/error.log")
        return False


if __name__ == "__main__":
    success = test_mysql_connection()
    sys.exit(0 if success else 1)

