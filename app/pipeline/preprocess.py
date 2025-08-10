import os
import subprocess
from rembg import remove
from PIL import Image
from lxml import etree


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
    cmd = [
    VTRACER_PATH,
    "--input", no_bg_path,
    "--output", output_svg_path,
    "--colormode", "color",
    "--hierarchical", "stacked",
    "--color_precision", "1",
    "--filter_speckle", "4",
    "--mode", "polygon",
    "--corner_threshold", "140",
    "--gradient_step", "30"
    ]
    subprocess.run(cmd, check=True)


    # === 3. Embed Ink/Stitch metadata ===
    embed_thread_colors(output_svg_path)

    return output_svg_path


def embed_thread_colors(svg_path: str):
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()

    nsmap = root.nsmap.copy()
    if None in nsmap:
        nsmap['svg'] = nsmap.pop(None)

    INKSTITCH_NS = "http://inkstitch.org/inkstitch"
    etree.register_namespace("inkstitch", INKSTITCH_NS)

    for elem in root.iter():
        style = elem.get("style")
        if not style:
            continue
        color = None
        for part in style.split(";"):
            if part.startswith("fill:") and "none" not in part:
                color = part.split(":", 1)[1]
                break
            if part.startswith("stroke:") and "none" not in part:
                color = part.split(":", 1)[1]
                break
        if color:
            elem.set(f"{{{INKSTITCH_NS}}}thread-color", color)
            # Minimal embroidery params:
            elem.set(f"{{{INKSTITCH_NS}}}fill-method", "auto")
            elem.set(f"{{{INKSTITCH_NS}}}stitch-method", "auto")
            elem.set(f"{{{INKSTITCH_NS}}}stitch-spacing", "2.0")

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
