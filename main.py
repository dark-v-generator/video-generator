import socket
import uvicorn
from src.core.config import settings
from src.core.logging_config import configure_logging, get_logger


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def run_fastapi_server():
    """Run the FastAPI server with dependency injection"""
    # Configure logging first
    configure_logging()
    
    logger = get_logger(__name__)
    logger.info("Starting FastAPI server with dependency injection architecture...")
    logger.info(f"Server will be available at: http://{get_local_ip()}:{settings.api_port}")
    logger.info("API Documentation: /docs")
    
    uvicorn.run(
        "src.main_fastapi:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"  # Ensure uvicorn uses INFO level
    )


def main():
    """Main application entry point"""
    run_fastapi_server()


if __name__ == "__main__":
    main()
