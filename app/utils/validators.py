"""Input validation and security utilities."""
import os
import magic
import logging
from PIL import Image
from io import BytesIO
from typing import Tuple, Optional
from fastapi import HTTPException
from xml.etree import ElementTree as ET
from app.pipeline.config import (
    MAX_FILE_SIZE_MB,
    MAX_IMAGE_SIZE,
    ALLOWED_EXTENSIONS,
    MAX_COLORS
)

def validate_file_size(file_size: int) -> bool:
    """Check if file size is within limits."""
    max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE_MB}MB"
        )
    return True

def validate_mime_type(content: bytes) -> Tuple[str, str]:
    """Validate file mime type and return file extension."""
    mime = magic.Magic(mime=True)
    mime_type = mime.from_buffer(content)
    
    # Add logging for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Detected MIME type: {mime_type}")
    
    mime_to_ext = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/svg+xml': '.svg',
        'text/xml': '.svg',  # Some systems identify SVG as text/xml
        'text/plain': '.svg'  # Some systems identify SVG as text/plain
    }
    
    ext = mime_to_ext.get(mime_type)
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    return mime_type, ext

def validate_image_content(content: bytes, mime_type: str) -> None:
    """Validate image dimensions and color count."""
    if mime_type == 'image/svg+xml':
        _validate_svg(content)
    else:
        _validate_raster_image(content)

def _validate_raster_image(content: bytes) -> None:
    """Validate raster image properties."""
    try:
        with Image.open(BytesIO(content)) as img:
            # Check dimensions
            if img.size[0] > MAX_IMAGE_SIZE[0] or img.size[1] > MAX_IMAGE_SIZE[1]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image dimensions exceed maximum of {MAX_IMAGE_SIZE[0]}x{MAX_IMAGE_SIZE[1]}"
                )
            
            # Convert to RGB if needed
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')
            
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image content: {str(e)}"
        )

def _validate_svg(content: bytes) -> None:
    """Validate SVG content and structure."""
    try:
        # Add logging for debugging
        
        logger = logging.getLogger(__name__)
        logger.info("Validating SVG content...")
        
        # Try to decode content as string first
        try:
            content_str = content.decode('utf-8')
            if '<?xml' not in content_str and '<svg' not in content_str:
                raise HTTPException(
                    status_code=400,
                    detail="File does not appear to be a valid SVG"
                )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid SVG encoding"
            )
        
        tree = ET.fromstring(content)
        
        # Remove potentially harmful elements
        for elem in tree.iter():
            # Remove scripts
            if elem.tag.lower().endswith('}script'):
                elem.clear()
            
            # Remove external references
            for attr in list(elem.attrib):
                if attr.lower() in ('href', 'xlink:href'):
                    if not elem.attrib[attr].startswith('#'):  # Allow internal refs
                        del elem.attrib[attr]
                        
        logger.info("SVG validation successful")
        
    except ET.ParseError:
        raise HTTPException(
            status_code=400,
            detail="Invalid SVG format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SVG validation error: {str(e)}"
        )
