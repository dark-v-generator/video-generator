from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import HTTPException
import os
import mimetypes
import logging

from .core.container import container
from .core.logging_config import configure_logging, get_logger
from .api.routers import histories, config, health, files, youtube_auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    configure_logging()
    
    logger = get_logger(__name__)
    logger.info("🚀 Video Generator API started")
    logger.info("📡 CORS Configuration:")
    logger.info("   ✓ Lovable.app domains: *.lovable.app")
    logger.info("   ✓ Lovable projects: *.lovableproject.com")
    logger.info("   ✓ Development: localhost and 127.0.0.1")
    logger.info("   ✓ Credentials: Allowed")
    logger.info("   ✓ Methods: All")
    logger.info("   ✓ Headers: All")
    logger.info("📋 Available endpoints:")
    logger.info("   - API Documentation: /docs")
    logger.info("   - Health check: GET /api/health/")
    logger.info("   - CORS test: GET /api/health/cors-test")
    logger.info("   - List histories: GET /api/histories/")
    logger.info("   - Scrap Reddit: POST /api/histories/scrap")
    logger.info("   - Generate video: POST /api/histories/generate-video")
    logger.info("   - Configuration: GET /api/config/")
    logger.info("   - Static files: /static/*")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Video Generator API shutting down")


# Create FastAPI application with lifespan handler
app = FastAPI(
    title="Video Generator API",
    description="API for generating videos from Reddit posts",
    version="1.0.0",
    lifespan=lifespan,
)


# Configure CORS for Lovable endpoints and development
allow_origins = [
    r"https:\/\/.*\.lovable\.app",
    r"https:\/\/.*\.lovable\.dev", 
    r"https:\/\/[a-zA-Z0-9\-]+\.lovableproject\.com",
    r"http:\/\/127\.0\.0\.1:.*",
    r"http:\/\/localhost:.*",
    r"http:\/\/192\.168\..*:.*",  # Local network access
    r"http:\/\/10\..*:.*",       # Private network ranges
    r"http:\/\/172\.(1[6-9]|2[0-9]|3[01])\..*:.*",  # Private network ranges
]
allow_origin_regex: str = f"({'|'.join(allow_origins)})"

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(histories.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(youtube_auth.router)

# Configure MIME types for static files to prevent module loading errors
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/json', '.json')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('text/html', '.html')

# Mount static files for React SPA
if os.path.exists("web/static"):
    # Mount all static files at /static to match Vite's generated paths (/static/assets/...)
    app.mount("/static", StaticFiles(directory="web/static", html=True), name="static")


@app.get("/")
async def root():
    """Serve the React SPA"""
    return await serve_spa()

async def serve_spa():
    """Serve the React SPA index.html"""
    static_file_path = "web/static/index.html"
    if os.path.exists(static_file_path):
        return FileResponse(static_file_path, media_type="text/html")
    else:
        # Fallback if frontend hasn't been built yet
        return HTMLResponse(
            """
            <html>
                <head><title>Video Generator</title></head>
                <body>
                    <h1>Video Generator API</h1>
                    <p>Frontend not built yet. Please run: <code>make build-frontend</code></p>
                    <p>API Documentation: <a href="/docs">/docs</a></p>
                </body>
            </html>
            """
        )

# Catch-all route for React Router (client-side routing)
# This MUST be defined AFTER static file mount to avoid conflicts
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """
    Catch all non-API routes and serve the React SPA
    This allows React Router to handle client-side routing
    """
    # Don't intercept API routes, docs, or static files
    if (full_path.startswith("api/") or 
        full_path.startswith("docs") or 
        full_path.startswith("static/") or
        full_path.startswith("openapi.json") or
        full_path.startswith("redoc") or
        full_path in ["favicon.ico", "robots.txt", "placeholder.svg"]):
        raise HTTPException(status_code=404, detail="Not found")
    
    # Serve the React SPA for all other routes
    return await serve_spa()





if __name__ == "__main__":
    import uvicorn
    from .core.config import settings

    uvicorn.run(
        "src.main_fastapi:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )