import os
import uuid
import subprocess
from app.pipeline.preprocess import preprocess_to_svg

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def export_with_inkstitch(svg_path: str, uid, output_dir: str = "storage/outputs") -> str:
    """
    Use Inkscape CLI (with Ink/Stitch installed) to export a DST file.
    """
    ensure_dir(output_dir)
    dst_name = f"{uid}.dst"
    dst_output_path = os.path.join(output_dir, dst_name)

    cmd = [
        "xvfb-run", "-a",
        "inkscape",
        svg_path,
        "--export-type=dst",
        f"--export-filename={dst_output_path}"
    ]
    subprocess.run(cmd, check=True)

    if not os.path.exists(dst_output_path):
        raise FileNotFoundError(f"DST not generated at {dst_output_path}")

    return dst_output_path

def run(input_image_path: str, uid) -> str:
    """
    Full pipeline:
    1. Preprocess image (remove bg, vectorize, metadata)
    2. Export to DST via Inkscape/InkStitch
    """
    ext = os.path.splitext(input_image_path)[1].lower()
    if ext == ".svg":
        svg_path = input_image_path
    else:
        svg_path = preprocess_to_svg(input_image_path, uid)
    dst_path = export_with_inkstitch(svg_path, uid)
    return dst_path
