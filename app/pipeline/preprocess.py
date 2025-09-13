import os
import subprocess
import logging
from rembg import remove
from PIL import Image
from lxml import etree
from .config import VTRACER_SETTINGS, STITCH_SETTINGS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
VTRACER_PATH = os.path.join(TOOLS_DIR, "vtracer")

PROCESSED_DIR = os.path.join(BASE_DIR, "storage", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

def preprocess_to_svg(input_image_path: str, uid) -> str:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    base = str(uid)
    no_bg_path = os.path.join(PROCESSED_DIR, f"{base}_no_bg.png")
    output_svg_path = os.path.join(PROCESSED_DIR, f"{base}_inkstitch.svg")

    # === 1. Remove background ===
    with open(input_image_path, "rb") as inp:
        result = remove(inp.read())
    with open(no_bg_path, "wb") as outp:
        outp.write(result)

    # (Optional) convert to RGB PNG with Pillow for safety
    img = Image.open(no_bg_path).convert("RGBA")
    img.save(no_bg_path)

    # === 2. Vectorize with vtracer ===
    cmd = [VTRACER_PATH, "--input", no_bg_path, "--output", output_svg_path]
    
    # Add all settings from config
    for key, value in VTRACER_SETTINGS.items():
        cmd.extend([f"--{key}", str(value)])
    subprocess.run(cmd, check=True)


    # === 3. Embed Ink/Stitch metadata ===
    embed_thread_colors(output_svg_path)

    return output_svg_path


def embed_thread_colors(svg_path: str):
    """
    Process SVG file to properly set up thread colors and embroidery parameters.
    Only processes fill colors and ensures proper thread changes.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()

    nsmap = root.nsmap.copy()
    if None in nsmap:
        nsmap['svg'] = nsmap.pop(None)

    INKSTITCH_NS = "http://inkstitch.org/inkstitch"
    etree.register_namespace("inkstitch", INKSTITCH_NS)
    
    # Track unique colors to manage thread changes
    processed_colors = set()
    first_color = True  # First color doesn't need a thread change
    
    for elem in root.iter('{%s}path' % nsmap.get('svg', '')):
        style = elem.get("style", "")
        if not style:
            continue
            
        # Extract fill color
        fill_color = None
        for part in style.split(";"):
            if part.startswith("fill:") and "none" not in part:
                fill_color = part.split(":", 1)[1].strip()
                break
                
        if not fill_color or fill_color == "none":
            continue
            
        # Set thread color
        elem.set(f"{{{INKSTITCH_NS}}}thread-color", fill_color)
        
        # Set embroidery parameters
        elem.set(f"{{{INKSTITCH_NS}}}fill-method", STITCH_SETTINGS['default_fill'])
        elem.set(f"{{{INKSTITCH_NS}}}stitch-method", "running")
        elem.set(f"{{{INKSTITCH_NS}}}stitch-spacing", str(STITCH_SETTINGS['spacing']))
        elem.set(f"{{{INKSTITCH_NS}}}running-stitch-length", str(STITCH_SETTINGS['running_stitch']))
        
        # Add thread change command if it's a new color (except for first color)
        if fill_color not in processed_colors:
            if not first_color:
                elem.set(f"{{{INKSTITCH_NS}}}thread-change", "true")
            processed_colors.add(fill_color)
            first_color = False
            
        # Remove stroke to prevent double-stitching
        new_style_parts = [p for p in style.split(";") if not p.startswith("stroke:")]
        new_style_parts.append("stroke:none")
        elem.set("style", ";".join(new_style_parts))

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
