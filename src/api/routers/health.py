from fastapi import APIRouter, Request
from datetime import datetime, timezone
import platform
import sys


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "python_version": sys.version,
        "platform": platform.system(),
    }


@router.get("/cors-test")
async def cors_test(request: Request):
    """CORS test endpoint to verify cross-origin requests work"""
    origin = request.headers.get("origin", "unknown")
    
    return {
        "message": "CORS is working!",
        "origin": origin,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cors_enabled": True,
        "allowed_patterns": [
            "*.lovable.app",
            "*.lovableproject.com",
            "localhost:*",
            "127.0.0.1:*"
        ]
    }
