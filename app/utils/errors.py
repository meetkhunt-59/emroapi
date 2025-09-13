"""Error handling and custom exceptions."""
from fastapi import HTTPException
from typing import Dict, Any

class EmbroError(Exception):
    """Base exception for embroidery processing errors."""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ImageProcessingError(EmbroError):
    """Raised when image processing fails."""
    pass

class VectorizationError(EmbroError):
    """Raised when vectorization fails."""
    pass

class StitchGenerationError(EmbroError):
    """Raised when stitch generation fails."""
    pass

def handle_embroidery_error(error: EmbroError) -> HTTPException:
    """Convert internal errors to HTTP exceptions."""
    status_codes = {
        ImageProcessingError: 400,
        VectorizationError: 500,
        StitchGenerationError: 500
    }
    
    return HTTPException(
        status_code=status_codes.get(type(error), 500),
        detail={
            "error": error.message,
            "type": error.__class__.__name__,
            "details": error.details
        }
    )
