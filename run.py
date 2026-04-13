#!/usr/bin/env python3
"""
Entry point — loads .env then starts uvicorn.
Run: python run.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
