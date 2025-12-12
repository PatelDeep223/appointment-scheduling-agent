#!/usr/bin/env python3
"""
Quick start script for the appointment scheduling agent
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8000))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    print(f"🚀 Starting Medical Appointment Scheduling Agent...")
    print(f"📡 Server will be available at http://{host}:{port}")
    print(f"📚 API docs at http://{host}:{port}/docs")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

