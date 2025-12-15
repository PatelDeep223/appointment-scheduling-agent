"""
Script to check database connection and table creation
Run this to verify MySQL setup
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from database import engine, init_db, Base
from sqlalchemy import inspect, text

def check_database():
    """Check database connection and tables"""
    print("🔍 Checking database connection...")
    
    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to database")
            print(f"   Version: {version[:50]}...")
        
        # Initialize database (create tables)
        print("\n📦 Creating tables...")
        init_db()
        
        # Check if tables exist
        print("\n📋 Checking tables...")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"✅ Found {len(tables)} table(s):")
            for table in tables:
                columns = inspector.get_columns(table)
                print(f"   - {table} ({len(columns)} columns)")
                
                # Show column details for bookings table
                if table == "bookings":
                    print(f"     Columns:")
                    for col in columns:
                        print(f"       • {col['name']}: {col['type']}")
        else:
            print("⚠️  No tables found")
        
        # Check bookings table structure
        if "bookings" in tables:
            print("\n✅ 'bookings' table exists and is ready!")
            
            # Try a test query
            try:
                from models.booking import Booking
                from sqlalchemy.orm import Session
                from database import SessionLocal
                
                db = SessionLocal()
                count = db.query(Booking).count()
                print(f"   Current bookings count: {count}")
                db.close()
            except Exception as e:
                print(f"   ⚠️  Could not query bookings: {e}")
        else:
            print("\n❌ 'bookings' table not found!")
            print("   Run init_db() to create tables")
        
    except Exception as e:
        print(f"\n❌ Database check failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)

