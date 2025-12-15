"""
Test MySQL database connection
Run this to verify your database credentials are correct
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

def test_connection():
    """Test database connection"""
    print("🔍 Testing MySQL Connection...")
    print("")
    
    # Get connection details
    database_url = os.getenv("DATABASE_URL")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "appointments_db")
    
    # Build connection string if not provided
    if not database_url:
        if db_password:
            # URL encode password to handle special characters like @, #, etc.
            encoded_password = quote_plus(db_password)
            database_url = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        else:
            print("❌ No DATABASE_URL or DB_PASSWORD found in .env file")
            print("")
            print("Please set one of these in your .env file:")
            print("  DATABASE_URL=mysql+pymysql://user:password@host:port/database?charset=utf8mb4")
            print("  OR")
            print("  DB_HOST=localhost")
            print("  DB_PORT=3306")
            print("  DB_USER=your_user")
            print("  DB_PASSWORD=your_password")
            print("  DB_NAME=your_database")
            return False
    
    print(f"Connection String: mysql+pymysql://{db_user}:***@{db_host}:{db_port}/{db_name}")
    print("")
    
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Test connection
        print("Testing connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"✅ Connection successful!")
            print(f"   MySQL version: {version[:60]}...")
            print("")
            
            # Check if database exists
            result = conn.execute(text("SELECT DATABASE()"))
            current_db = result.fetchone()[0]
            print(f"✅ Connected to database: {current_db}")
            print("")
            
            # Check if user has permissions
            result = conn.execute(text("SELECT USER()"))
            current_user = result.fetchone()[0]
            print(f"✅ Connected as user: {current_user}")
            print("")
            
            # Test table creation permission
            try:
                conn.execute(text("CREATE TABLE IF NOT EXISTS test_permissions (id INTEGER)"))
                conn.execute(text("DROP TABLE test_permissions"))
                print("✅ User has CREATE TABLE permission")
            except Exception as e:
                print(f"⚠️  User may not have CREATE TABLE permission: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("")
        print("Troubleshooting:")
        print("1. Check if MySQL is running: sudo service mysql status")
        print("2. Verify credentials in .env file")
        print("3. Check if user exists: mysql -u root -p -e \"SELECT User FROM mysql.user;\"")
        print("4. Check if database exists: mysql -u root -p -e \"SHOW DATABASES;\"")
        print("5. Verify MySQL bind-address in /etc/mysql/mysql.conf.d/mysqld.cnf")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

