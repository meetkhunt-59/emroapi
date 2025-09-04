"""Configuration settings for the embroidery pipeline."""

# Image processing settings
MAX_COLORS = 10
MAX_IMAGE_SIZE = (4000, 4000)  # Max dimensions
MAX_FILE_SIZE_MB = 20

# Thread and stitch settings
STITCH_SETTINGS = {
    "spacing": 3.0,  # mm between stitches
    "default_fill": "tatami",  # or "auto"
    "running_stitch": 2.0,  # mm between running stitches
    "density": 0.4  # Lines per mm
}

# File type settings
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg'}

# Vectorization settings
VTRACER_SETTINGS = {
    "colormode": "color",
    "hierarchical": "stacked",
    "color_precision": 5,
    "filter_speckle": 6,
    "mode": "spline",
    "corner_threshold": 70,
    "gradient_step": 6,
    "path_precision": 2,
    "segment_length": 4.0  # For smoother curves
}
