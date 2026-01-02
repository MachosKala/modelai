"""
AI Model Generator - Server Runner
Run this file to start the backend server.
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("")
    print("=" * 50)
    print("  AI Model Generator MVP")
    print("=" * 50)
    print("")
    print("  Starting server...")
    print("")
    print(f"  API Docs:  http://localhost:{settings.port}/docs")
    print(f"  Health:    http://localhost:{settings.port}/health")
    print("")
    print("=" * 50)
    print("")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
