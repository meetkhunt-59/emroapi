"""Configuration settings for the embroidery pipeline."""

# Image processing settings
MAX_COLORS = 12
MAX_IMAGE_SIZE = (4000, 4000)  # Max dimensions
MAX_FILE_SIZE_MB = 20

# Thread and stitch settings
STITCH_SETTINGS = {
    "spacing": 0.4,  # mm between rows (row_spacing_mm). 0.4 = full-coverage density
    "default_fill": "tatami",  # or "auto"
    "running_stitch": 2.5,  # mm between running stitches (safe zone: 1.5 - 3.0 mm)
    "expand_mm": 0.2,  # mm to expand fills for pull/push compensation (0.15 - 0.3 mm standard)
    "pull_compensation_mm": 0.2  # mm for satin pull compensation
}

# File type settings
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg'}

# Vectorization settings
VTRACER_SETTINGS = {
    "colormode": "color",
    "hierarchical": "cutout",
    "color_precision": 6,  # 1-8 scale; 6 preserves subtle gradients for logos
    "filter_speckle": 4,  # px; low value keeps small details (dots, thin strokes)
    "mode": "spline",
    "corner_threshold": 70,
    "gradient_step": 6,
    "path_precision": 5,  # decimal places; 5+ avoids rounding drift at embroidery scale
    "segment_length": 4.0  # curve segmentation granularity
}

# Canvas / design settings
MAX_DESIGN_DIMENSION_MM = 200  # Scale designs to fit within this (≈8" hoop)
MIN_PATH_AREA = 1.0           # sq mm — paths smaller than this are removed as micro-fragments
