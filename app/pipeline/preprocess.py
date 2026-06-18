import os
import re
import subprocess
import logging
import shutil
import colorsys
import numpy as np
from lxml import etree
from svgpathtools import Document, parse_path, Line, CubicBezier, QuadraticBezier, Arc, Path
from svgpathtools.parser import parse_transform
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from .config import (
    VTRACER_SETTINGS, STITCH_SETTINGS, MAX_COLORS,
    MAX_DESIGN_DIMENSION_MM, MIN_PATH_AREA,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
VTRACER_PATH = os.path.join(TOOLS_DIR, "vtracer")

PROCESSED_DIR = os.path.join(BASE_DIR, "storage", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

SVG_NS = "http://www.w3.org/2000/svg"
INKSTITCH_NS = "http://inkstitch.org/inkstitch"

# Identity matrix for transform accumulation
_IDENTITY = np.eye(3)


# ---------------------------------------------------------------------------
#  SVG geometry normalisation (viewBox + transform baking)
# ---------------------------------------------------------------------------

def _strip_units(value: str) -> float:
    """Strip CSS unit suffixes and return a float. Handles px, mm, pt, in, cm."""
    if not value:
        return 0.0
    value = value.strip()
    # Conversion factors to px (SVG default user unit)
    unit_factors = {
        'px': 1.0, 'mm': 3.7795275591, 'cm': 37.795275591,
        'in': 96.0, 'pt': 1.3333333333, 'pc': 16.0, 'em': 16.0,
    }
    for unit, factor in unit_factors.items():
        if value.endswith(unit):
            try:
                return float(value[:-len(unit)].strip()) * factor
            except ValueError:
                return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def ensure_viewbox(svg_path: str):
    """
    Guarantee the SVG has a viewBox attribute.
    If missing, construct one from width/height (stripping units).
    Falls back to scanning path bounding boxes.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()

    if root.get("viewBox"):
        logger.info(f"viewBox already present: {root.get('viewBox')}")
        return

    w_str = root.get("width", "")
    h_str = root.get("height", "")
    w = _strip_units(w_str)
    h = _strip_units(h_str)

    if w > 0 and h > 0:
        root.set("viewBox", f"0 0 {w:.4f} {h:.4f}")
        # Normalise width/height to unitless values matching the viewBox
        root.set("width", f"{w:.4f}")
        root.set("height", f"{h:.4f}")
        logger.info(f"Created viewBox from width/height: 0 0 {w:.4f} {h:.4f}")
    else:
        # Fallback: compute bounding box from all path elements
        logger.warning("No width/height on SVG root — computing viewBox from content")
        try:
            doc = Document(svg_path)
            xmin, xmax, ymin, ymax = doc.get_bbox()
            vb_w = xmax - xmin
            vb_h = ymax - ymin
            if vb_w > 0 and vb_h > 0:
                root.set("viewBox", f"{xmin:.4f} {ymin:.4f} {vb_w:.4f} {vb_h:.4f}")
                root.set("width", f"{vb_w:.4f}")
                root.set("height", f"{vb_h:.4f}")
                logger.info(f"Created viewBox from content bbox: {xmin:.1f} {ymin:.1f} {vb_w:.1f} {vb_h:.1f}")
            else:
                logger.error("Could not determine SVG dimensions for viewBox")
                return
        except Exception as e:
            logger.error(f"Failed to compute viewBox from content: {e}")
            return

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


def _apply_matrix_to_point(matrix: np.ndarray, x: float, y: float):
    """Apply a 3×3 affine transform matrix to a 2D point."""
    pt = np.array([x, y, 1.0])
    result = matrix @ pt
    return result[0], result[1]


def _apply_matrix_to_complex(matrix: np.ndarray, c: complex) -> complex:
    """Apply a 3×3 affine transform to a complex point (real=x, imag=y)."""
    rx, ry = _apply_matrix_to_point(matrix, c.real, c.imag)
    return complex(rx, ry)


def _transform_segment(seg, matrix: np.ndarray):
    """
    Apply an affine transform matrix to an svgpathtools path segment.
    Returns a new segment with transformed control points.
    """
    if isinstance(seg, Line):
        return Line(
            _apply_matrix_to_complex(matrix, seg.start),
            _apply_matrix_to_complex(matrix, seg.end),
        )
    elif isinstance(seg, CubicBezier):
        return CubicBezier(
            _apply_matrix_to_complex(matrix, seg.start),
            _apply_matrix_to_complex(matrix, seg.control1),
            _apply_matrix_to_complex(matrix, seg.control2),
            _apply_matrix_to_complex(matrix, seg.end),
        )
    elif isinstance(seg, QuadraticBezier):
        return QuadraticBezier(
            _apply_matrix_to_complex(matrix, seg.start),
            _apply_matrix_to_complex(matrix, seg.control),
            _apply_matrix_to_complex(matrix, seg.end),
        )
    elif isinstance(seg, Arc):
        # For arcs, transform start/end and radii.
        # Non-uniform scaling can distort arcs, but for translate/uniform-scale
        # this is correct. For safety, approximate with cubics if skew detected.
        new_start = _apply_matrix_to_complex(matrix, seg.start)
        new_end = _apply_matrix_to_complex(matrix, seg.end)
        # Scale radii by the average scale factor
        sx = np.sqrt(matrix[0, 0] ** 2 + matrix[1, 0] ** 2)
        sy = np.sqrt(matrix[0, 1] ** 2 + matrix[1, 1] ** 2)
        new_radius = complex(seg.radius.real * sx, seg.radius.imag * sy)
        # Adjust rotation by the rotation component of the matrix
        rotation_deg = seg.rotation
        if abs(matrix[0, 0]) > 1e-10:
            import math
            rotation_deg += math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
        return Arc(
            new_start, new_radius, rotation_deg,
            seg.large_arc, seg.sweep, new_end,
        )
    else:
        # Unknown segment type — return as-is (shouldn't happen)
        logger.warning(f"Unknown segment type in _transform_segment: {type(seg)}")
        return seg


def bake_transforms(svg_path: str):
    """
    Flatten ALL transform attributes into absolute path coordinates.
    Recursively accumulates group transforms and applies them to child elements.
    After this function runs, NO element in the SVG has a transform attribute.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()
    ns = root.nsmap.get(None, SVG_NS)

    baked_count = 0

    def _get_transform_matrix(elem):
        """Parse the transform attribute of an element into a 3×3 matrix."""
        t = elem.get("transform")
        if not t or not t.strip():
            return _IDENTITY.copy()
        try:
            return parse_transform(t)
        except Exception as e:
            logger.warning(f"Failed to parse transform '{t}': {e}")
            return _IDENTITY.copy()

    def _bake_recursive(elem, parent_matrix):
        """Recursively bake transforms down the tree."""
        nonlocal baked_count
        local_matrix = _get_transform_matrix(elem)
        cumulative = parent_matrix @ local_matrix

        # Remove the transform attribute from this element
        if elem.get("transform") is not None:
            del elem.attrib["transform"]

        tag = elem.tag
        if isinstance(tag, str):
            # Strip namespace for comparison
            local_tag = tag.split("}")[-1] if "}" in tag else tag
        else:
            local_tag = ""

        # Apply cumulative transform to path elements
        if local_tag == "path" and not np.allclose(cumulative, _IDENTITY):
            d = elem.get("d", "").strip()
            if d:
                try:
                    path_obj = parse_path(d)
                    new_segments = []
                    for seg in path_obj:
                        new_segments.append(_transform_segment(seg, cumulative))
                    new_path = Path(*new_segments)
                    elem.set("d", new_path.d())
                    baked_count += 1
                except Exception as e:
                    logger.warning(f"Failed to bake transform into path d: {e}")

            # Reset cumulative for children (path has no children, but be safe)
            for child in elem:
                _bake_recursive(child, _IDENTITY.copy())
            return

        # For groups and other containers, recurse with accumulated transform
        for child in list(elem):
            _bake_recursive(child, cumulative.copy())

    # Start recursion from root
    root_matrix = _get_transform_matrix(root)
    if root.get("transform") is not None:
        del root.attrib["transform"]

    for child in list(root):
        _bake_recursive(child, root_matrix.copy())

    if baked_count > 0:
        logger.info(f"Baked transforms on {baked_count} path elements")
    else:
        logger.info("No transforms to bake (all paths already in absolute coords)")

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


def flatten_svg_dom(svg_path: str):
    """
    Flattens the SVG DOM structure by moving all <path> elements directly to the root,
    and removing everything else (groups, defs, clipPaths, nested SVGs) except safe metadata.
    Must run AFTER bake_transforms so paths already have absolute coordinates.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()
    ns = root.nsmap.get(None, SVG_NS)

    # Collect all paths from anywhere in the document, EXCEPT those inside <defs>
    paths = []
    for p in root.iter(f'{{{ns}}}path'):
        is_def = False
        ancestor = p.getparent()
        while ancestor is not None:
            tag = ancestor.tag.split("}")[-1] if "}" in ancestor.tag else ancestor.tag
            if tag == "defs":
                is_def = True
                break
            ancestor = ancestor.getparent()
        if not is_def:
            paths.append(p)
            
    # Strip clip-path attributes from paths
    for p in paths:
        if "clip-path" in p.attrib:
            del p.attrib["clip-path"]
            
    # Collect safe elements to keep at root level
    safe_elements = []
    for elem in list(root):
        if not isinstance(elem.tag, str):
            continue
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        # Keep style, namedview, metadata, titles, and defs (for gradients)
        if tag in ("style", "namedview", "metadata", "title", "desc", "defs"):
            safe_elements.append(elem)
            
    # Clear all children of the root
    for child in list(root):
        root.remove(child)
        
    # Append safe elements back
    for elem in safe_elements:
        root.append(elem)
        
    # Append all paths directly to root
    for p in paths:
        root.append(p)
        
    logger.info(f"Flattened SVG DOM: moved {len(paths)} paths to root and removed nested groups/clipPaths.")
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# ---------------------------------------------------------------------------
#  Color utilities
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str):
    """Parse any CSS hex color (#RGB, #RRGGBB) into (r,g,b) 0-255 tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _rgb_to_lab(r, g, b):
    """Approximate sRGB → CIELAB conversion for perceptual color distance."""
    # Linearise sRGB
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    rl, gl, bl = lin(r), lin(g), lin(b)

    # sRGB → XYZ (D65)
    x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl
    y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl
    z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl

    # XYZ → Lab
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t):
        return t ** (1/3) if t > 0.008856 else 7.787 * t + 16/116

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return (L, a, b_val)


def _color_distance(lab1, lab2):
    """Euclidean distance in CIELAB space (≈ ΔE*ab)."""
    return sum((a - b) ** 2 for a, b in zip(lab1, lab2)) ** 0.5


# ---------------------------------------------------------------------------
#  CSS class → inline fill resolution
# ---------------------------------------------------------------------------

def _parse_css_classes(style_text: str) -> dict:
    """Parse a CSS <style> block and return {class_name: {prop: value}} dict."""
    result = {}
    for match in re.finditer(r'\.([\w-]+)\s*\{([^}]*)\}', style_text):
        class_name = match.group(1)
        props = {}
        for prop_match in re.finditer(r'([\w-]+)\s*:\s*([^;]+)', match.group(2)):
            props[prop_match.group(1).strip()] = prop_match.group(2).strip()
        result[class_name] = props
    return result


def resolve_css_colors(root):
    """
    Parse <style> blocks and resolve CSS class fill/stroke into inline attributes
    so downstream functions (embed_thread_colors, overlap cleanup) can see them.
    """
    nsmap = root.nsmap.copy()
    svg_ns = nsmap.get(None, SVG_NS)

    # Collect all <style> blocks
    css_classes = {}
    for style_el in root.iter(f'{{{svg_ns}}}style'):
        if style_el.text:
            css_classes.update(_parse_css_classes(style_el.text))

    if not css_classes:
        return

    logger.info(f"Resolved {len(css_classes)} CSS classes: {list(css_classes.keys())}")

    # Apply to elements with class attributes
    for elem in root.iter():
        cls_attr = (elem.get("class") or "").strip()
        if not cls_attr or cls_attr not in css_classes:
            continue

        props = css_classes[cls_attr]

        # Set fill as inline attribute if defined in CSS and not already inline
        if "fill" in props and not elem.get("fill"):
            fill_val = props["fill"]
            if fill_val.lower() != "none":
                elem.set("fill", fill_val)
            else:
                elem.set("fill", "none")

        # Set stroke as inline attribute if defined in CSS
        if "stroke" in props and not elem.get("stroke"):
            elem.set("stroke", props["stroke"])

        if "stroke-width" in props and not elem.get("stroke-width"):
            elem.set("stroke-width", props["stroke-width"])


# ---------------------------------------------------------------------------
#  Geometry helpers (Shapely ↔ SVG)
# ---------------------------------------------------------------------------

def is_filled_path(element) -> bool:
    """Check if an SVG XML element has a fill color (i.e. is a filled path, not a stroke)."""
    if element is None:
        return False

    style = element.get("style", "")
    fill = element.get("fill", "")

    # Check style first
    if style:
        for part in style.split(";"):
            part_strip = part.strip()
            if part_strip.startswith("fill:"):
                fill_style = part_strip.split(":", 1)[1].strip().lower()
                return fill_style != "none"

    if fill:
        return fill.strip().lower() != "none"

    # Standard SVG default fill is black, so it is filled
    return True


def _is_stroke_path(element) -> bool:
    """Detect if an element was originally a stroke (border) path."""
    if element is None:
        return False

    stroke = element.get("stroke", "")
    style = element.get("style", "")

    if stroke and stroke.lower() != "none":
        return True

    if style:
        for part in style.split(";"):
            part_strip = part.strip()
            if part_strip.startswith("stroke:") and "none" not in part_strip:
                return True

    return False


def _is_thin_border(geom, threshold_ratio=0.08) -> bool:
    """
    Heuristic: a path is a thin border if its area is very small relative
    to its bounding-box area (i.e. it's a thin ring, not a solid fill).
    """
    if geom is None or geom.is_empty:
        return False
    try:
        minx, miny, maxx, maxy = geom.bounds
        bbox_area = (maxx - minx) * (maxy - miny)
        if bbox_area < 0.01:
            return True
        ratio = geom.area / bbox_area
        return ratio < threshold_ratio
    except Exception:
        return False


def path_to_shapely(path, num_samples=30):
    """Convert an svgpathtools Path object to a Shapely Polygon or MultiPolygon."""
    if not path or len(path) == 0:
        return None

    subpaths = path.continuous_subpaths()
    polygons = []

    for subpath in subpaths:
        points = []
        for segment in subpath:
            seg_type = segment.__class__.__name__
            if seg_type == 'Line':
                points.append((segment.start.real, segment.start.imag))
                points.append((segment.end.real, segment.end.imag))
            else:
                for idx in range(num_samples):
                    t = idx / (num_samples - 1)
                    pt = segment.point(t)
                    points.append((pt.real, pt.imag))

        if len(points) >= 3:
            if points[0] != points[-1]:
                points.append(points[0])
            try:
                poly = Polygon(points)
                if not poly.is_valid:
                    poly = poly.buffer(0.0)
                if not poly.is_empty:
                    polygons.append(poly)
            except Exception as e:
                logger.warning(f"Error converting subpath to Shapely polygon: {e}")

    if not polygons:
        return None

    try:
        return unary_union(polygons)
    except Exception as e:
        logger.error(f"Error unioning polygons in path_to_shapely: {e}")
        return None


def shapely_to_svg_path(geom) -> str:
    """Convert a Shapely geometry back into SVG path d-attribute syntax."""
    if geom is None or geom.is_empty:
        return ""

    if geom.geom_type == 'Polygon':
        ext_coords = list(geom.exterior.coords)
        if not ext_coords:
            return ""
        path_str = (
            f"M {ext_coords[0][0]:.3f} {ext_coords[0][1]:.3f} "
            + " ".join(f"L {c[0]:.3f} {c[1]:.3f}" for c in ext_coords[1:])
            + " Z"
        )
        for interior in geom.interiors:
            int_coords = list(interior.coords)
            if int_coords:
                path_str += (
                    f" M {int_coords[0][0]:.3f} {int_coords[0][1]:.3f} "
                    + " ".join(f"L {c[0]:.3f} {c[1]:.3f}" for c in int_coords[1:])
                    + " Z"
                )
        return path_str

    elif geom.geom_type == 'MultiPolygon':
        return " ".join(filter(None, (shapely_to_svg_path(p) for p in geom.geoms)))

    elif geom.geom_type == 'GeometryCollection':
        return " ".join(
            filter(None, (
                shapely_to_svg_path(g) for g in geom.geoms
                if g.geom_type in ('Polygon', 'MultiPolygon')
            ))
        )

    return ""


# ---------------------------------------------------------------------------
#  Overlap cleanup (stroke-aware)
# ---------------------------------------------------------------------------

def cleanup_svg_overlaps(input_path: str, output_path: str):
    """
    Boolean overlap cleanup on the SVG file.
    For each filled path, subtract the union of all filled paths layered above it.
    Skips thin border / stroke paths so outlines are preserved.
    """
    logger.info(f"Cleaning up overlaps in SVG {input_path} -> {output_path}")
    try:
        doc = Document(input_path)
        paths = doc.paths()

        if not paths:
            logger.info("No paths found in SVG for overlap cleanup")
            shutil.copy(input_path, output_path)
            return

        geometries = []
        is_filled = []
        skip_overlap = []  # True for paths that should NOT participate in subtraction

        for path in paths:
            elem = path.element
            filled = is_filled_path(elem)
            stroke = _is_stroke_path(elem)
            is_filled.append(filled)

            if filled:
                geom = path_to_shapely(path)
                geometries.append(geom)
                # Skip subtraction for paths that are thin borders or have strokes
                should_skip = stroke or (geom is not None and _is_thin_border(geom))
                skip_overlap.append(should_skip)
            else:
                geometries.append(None)
                skip_overlap.append(True)

        n = len(geometries)
        for i in range(n - 2, -1, -1):
            geom = geometries[i]
            if geom is None or geom.is_empty or skip_overlap[i]:
                continue

            upper_geoms = []
            for j in range(i + 1, n):
                if (is_filled[j]
                        and not skip_overlap[j]
                        and geometries[j] is not None
                        and not geometries[j].is_empty):
                    upper_geoms.append(geometries[j])

            if not upper_geoms:
                continue

            try:
                union_upper = unary_union(upper_geoms)
                new_geom = geom.difference(union_upper)
                geometries[i] = new_geom
            except Exception as e:
                logger.error(f"Error subtracting overlap for path {i}: {e}")

        parent_map = {c: p for p in doc.tree.iter() for c in p}

        for i, path in enumerate(paths):
            geom = geometries[i]
            element = path.element

            if is_filled[i] and not skip_overlap[i]:
                if geom is None or geom.is_empty or (hasattr(geom, 'area') and geom.area < 0.1):
                    parent = parent_map.get(element)
                    if parent is not None:
                        parent.remove(element)
                else:
                    new_d = shapely_to_svg_path(geom)
                    if new_d:
                        element.set('d', new_d)
                    else:
                        parent = parent_map.get(element)
                        if parent is not None:
                            parent.remove(element)

        doc.save(output_path)
        logger.info(f"Overlap cleanup completed successfully for {output_path}")

    except Exception as e:
        logger.error(f"Failed to clean up overlaps: {e}", exc_info=True)
        shutil.copy(input_path, output_path)


# ---------------------------------------------------------------------------
#  SVG optimization (scour)
# ---------------------------------------------------------------------------

def optimize_svg(input_path: str, output_path: str):
    """Optimize SVG using scour."""
    logger.info(f"Optimizing SVG {input_path} -> {output_path}")
    from scour import scour
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            svg_data = f.read()

        options = scour.sanitizeOptions(options=None)
        options.keep_editor_data = True
        options.enable_viewboxing = False  # Don't recalculate viewBox — we set it in resize_canvas
        options.newlines = False

        optimized = scour.scourString(svg_data, options=options)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(optimized)
        logger.info(f"SVG optimized successfully at {output_path}")
    except Exception as e:
        logger.error(f"Failed to optimize SVG with scour: {e}")
        shutil.copy(input_path, output_path)


# ---------------------------------------------------------------------------
#  Color quantization (for raster-sourced SVGs)
# ---------------------------------------------------------------------------

def quantize_svg_colors(svg_path: str, max_colors: int = MAX_COLORS):
    """
    Reduce the number of unique fill colors in an SVG to ≤ max_colors
    using perceptual LAB color distance clustering.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()
    ns = root.nsmap.get(None, SVG_NS)

    # Collect all unique fill colors
    color_elements = {}  # hex_upper -> [elements]
    for elem in root.iter(f'{{{ns}}}path'):
        fill = elem.get("fill", "").strip()
        if not fill or fill.lower() == "none":
            continue
        key = fill.upper()
        color_elements.setdefault(key, []).append(elem)

    unique_colors = list(color_elements.keys())
    logger.info(f"Color quantization: {len(unique_colors)} unique colors, target ≤ {max_colors}")

    if len(unique_colors) <= max_colors:
        return  # No quantization needed

    # Convert to LAB
    color_labs = {}
    for c in unique_colors:
        rgb = _hex_to_rgb(c)
        if rgb:
            color_labs[c] = _rgb_to_lab(*rgb)
        else:
            color_labs[c] = (50, 0, 0)  # fallback mid-grey

    # Simple greedy clustering: pick max_colors centroids by farthest-first
    centroids = [unique_colors[0]]
    while len(centroids) < max_colors:
        best_color = None
        best_dist = -1
        for c in unique_colors:
            if c in centroids:
                continue
            min_dist = min(_color_distance(color_labs[c], color_labs[cen]) for cen in centroids)
            if min_dist > best_dist:
                best_dist = min_dist
                best_color = c
        if best_color is None:
            break
        centroids.append(best_color)

    # Assign each color to nearest centroid
    color_map = {}
    for c in unique_colors:
        if c in centroids:
            color_map[c] = c
        else:
            nearest = min(centroids, key=lambda cen: _color_distance(color_labs[c], color_labs[cen]))
            color_map[c] = nearest

    # Apply remapping
    remapped_count = 0
    for original, target in color_map.items():
        if original != target:
            for elem in color_elements[original]:
                elem.set("fill", target)
                remapped_count += 1

    logger.info(f"Color quantization: remapped {remapped_count} elements, {len(set(color_map.values()))} colors remain")
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------------------
#  Path merging + micro-fragment removal
# ---------------------------------------------------------------------------

def remove_micro_fragments(svg_path: str, min_area: float = MIN_PATH_AREA):
    """
    Remove paths whose area falls below min_area (micro-fragments / speckles).

    This replaces the old merge_same_color_paths() which destructively
    converted Bézier curves to straight-line polygons via Shapely
    re-serialization.  We now use Shapely ONLY for the area check —
    the original path d-attribute is never touched.

    For raster-sourced SVGs vtracer --hierarchical cutout already resolves
    inter-color overlap at vectorization time, so geometric merging is
    unnecessary and harmful to curve fidelity.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()
    ns = root.nsmap.get(None, SVG_NS)

    try:
        doc = Document(svg_path)
        svg_paths = doc.paths()
    except Exception as e:
        logger.error(f"Failed to parse SVG for micro-fragment removal: {e}")
        return

    xml_paths = list(root.iter(f'{{{ns}}}path'))
    parent_map = {c: p for p in root.iter() for c in p}
    removed = 0

    for idx, svg_p in enumerate(svg_paths):
        if idx >= len(xml_paths):
            break
        elem = xml_paths[idx]
        fill = elem.get("fill", "").strip().upper()
        if not fill or fill == "NONE":
            continue

        # Use Shapely only for area measurement — never re-serialise the path
        geom = path_to_shapely(svg_p)
        if geom is None or geom.is_empty or geom.area < min_area:
            parent = parent_map.get(elem)
            if parent is not None:
                parent.remove(elem)
                removed += 1

    logger.info(f"Micro-fragment removal: removed {removed} paths below {min_area} sq-px area")
    if removed > 0:
        tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# Keep the old name as an alias so existing call-sites don't break
def merge_same_color_paths(svg_path: str, min_area: float = MIN_PATH_AREA):
    """Deprecated alias → delegates to remove_micro_fragments()."""
    remove_micro_fragments(svg_path, min_area)


# ---------------------------------------------------------------------------
#  Canvas resize
# ---------------------------------------------------------------------------

def remove_empty_paths(svg_path: str):
    """
    Remove paths with empty or trivially small d-attributes.
    These are artifacts from Inkscape object-to-path conversion.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()
    ns = root.nsmap.get(None, SVG_NS)

    parent_map = {c: p for p in root.iter() for c in p}
    removed = 0

    for elem in list(root.iter(f'{{{ns}}}path')):
        d = (elem.get('d') or '').strip()
        # Remove paths with no data, or trivially short data (just a moveto, no actual shape)
        if not d or len(d) <= 5:
            parent = parent_map.get(elem)
            if parent is not None:
                parent.remove(elem)
                removed += 1

    if removed > 0:
        logger.info(f"Removed {removed} empty/trivial paths")
        tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


def resize_canvas(svg_path: str, target_width_mm: float = None, target_height_mm: float = None, max_dim_mm: float = MAX_DESIGN_DIMENSION_MM):
    """
    Scale the SVG so it fits within target dimensions or max_dim_mm.
    Keeps path coordinates as they are (no coordinate scaling).
    Updates width and height to match the new dimensions (in mm),
    and ensures viewBox preserves the original unscaled coordinates.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()

    viewbox = root.get("viewBox")
    if not viewbox:
        logger.warning("No viewBox found, skipping canvas resize")
        return

    parts = viewbox.split()
    if len(parts) != 4:
        return

    try:
        min_x, min_y, width_px, height_px = (float(p) for p in parts)
    except ValueError:
        return

    if width_px <= 0 or height_px <= 0:
        return

    # SVG px is typically 96dpi -> 1px = 25.4/96 mm = 1 / 3.7795275591 mm
    width_mm_current = width_px / 3.7795275591
    height_mm_current = height_px / 3.7795275591

    scale_factor = 1.0

    if target_width_mm is not None or target_height_mm is not None:
        # Scale to fit within the specified width and height (preserving aspect ratio)
        scale_x = target_width_mm / width_mm_current if target_width_mm else float('inf')
        scale_y = target_height_mm / height_mm_current if target_height_mm else float('inf')
        scale_factor = min(scale_x, scale_y)
    else:
        longest_mm = max(width_mm_current, height_mm_current)
        if longest_mm <= max_dim_mm:
            logger.info(f"Canvas {width_mm_current:.1f}×{height_mm_current:.1f} mm already within {max_dim_mm}mm, setting mm units.")
            scale_factor = 1.0
        else:
            scale_factor = max_dim_mm / longest_mm

    new_w_mm = width_mm_current * scale_factor
    new_h_mm = height_mm_current * scale_factor

    # Keep path coordinates as they are.
    # Set viewBox to preserve the original coordinate space (unscaled).
    root.set("viewBox", viewbox)
    root.set("width", f"{new_w_mm:.4f}mm")
    root.set("height", f"{new_h_mm:.4f}mm")

    logger.info(f"Canvas resized: width/height updated to {new_w_mm:.1f}mm × {new_h_mm:.1f}mm (viewBox preserved)")
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------------------
#  Embroidery metadata embedding
# ---------------------------------------------------------------------------

def embed_thread_colors(svg_path: str):
    """
    Process SVG file to set up thread colors and embroidery parameters.
    Resolves CSS class colors first, then processes all filled paths.
    Configures size-dependent automatic underlays and thread changes.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(svg_path, parser)
    root = tree.getroot()

    # Step 1: Resolve CSS class colors to inline attributes
    resolve_css_colors(root)

    nsmap = root.nsmap.copy()
    if None in nsmap:
        nsmap['svg'] = nsmap.pop(None)

    etree.register_namespace("inkstitch", INKSTITCH_NS)

    # Load path geometries for size-dependent underlay configuration
    try:
        doc = Document(svg_path)
        geoms = doc.paths()
    except Exception as e:
        logger.error(f"Failed to parse path geometries for underlay configuration: {e}")
        geoms = []

    # Track unique colors for thread changes
    processed_colors = set()
    first_color = True
    processed_count = 0

    for idx, elem in enumerate(root.iter('{%s}path' % nsmap.get('svg', ''))):
        style = elem.get("style", "")
        fill = elem.get("fill", "")

        # Extract fill color
        fill_color = None
        if style:
            for part in style.split(";"):
                part_strip = part.strip()
                if part_strip.startswith("fill:") and "none" not in part_strip:
                    fill_color = part_strip.split(":", 1)[1].strip()
                    break

        if not fill_color and fill and fill.strip().lower() != "none":
            fill_color = fill.strip()

        if not fill_color or fill_color == "none":
            continue

        processed_count += 1

        # Set thread color
        elem.set(f"{{{INKSTITCH_NS}}}thread-color", fill_color)

        # Set embroidery parameters
        elem.set(f"{{{INKSTITCH_NS}}}fill-method", STITCH_SETTINGS['default_fill'])
        elem.set(f"{{{INKSTITCH_NS}}}stitch-method", "running")
        elem.set(f"{{{INKSTITCH_NS}}}stitch-spacing", str(STITCH_SETTINGS['spacing']))
        elem.set(f"{{{INKSTITCH_NS}}}running-stitch-length", str(STITCH_SETTINGS['running_stitch']))

        # Pull & push compensation
        elem.set(f"{{{INKSTITCH_NS}}}expand_mm", str(STITCH_SETTINGS.get('expand_mm', 0.2)))
        elem.set(f"{{{INKSTITCH_NS}}}expand-mm", str(STITCH_SETTINGS.get('expand_mm', 0.2)))
        elem.set(f"{{{INKSTITCH_NS}}}pull_compensation_mm", str(STITCH_SETTINGS.get('pull_compensation_mm', 0.2)))
        elem.set(f"{{{INKSTITCH_NS}}}pull-compensation-mm", str(STITCH_SETTINGS.get('pull_compensation_mm', 0.2)))

        # Size-dependent underlay
        geom = geoms[idx] if idx < len(geoms) else None
        enable_underlay = False
        if geom is not None and len(geom) > 0:
            try:
                shapely_geom = path_to_shapely(geom)
                if shapely_geom is not None and not shapely_geom.is_empty:
                    area = shapely_geom.area
                    minx, miny, maxx, maxy = shapely_geom.bounds
                    width = maxx - minx
                    height = maxy - miny
                    if area >= 100 and min(width, height) >= 10:
                        enable_underlay = True
            except Exception as e:
                logger.warning(f"Failed to calculate path size for underlay: {e}")

        if enable_underlay:
            for attr, val in [
                ("fill_underlay", "true"), ("fill_underlay_angle", "90"),
                ("fill_underlay_row_spacing_mm", "3.0"),
                ("fill_underlay_max_stitch_length_mm", "4.0"),
                ("fill_underlay_inset_mm", "1.0"),
                ("fill-underlay", "true"), ("fill-underlay-angle", "90"),
                ("fill-underlay-row-spacing", "3.0"),
                ("fill-underlay-max-stitch-length", "4.0"),
                ("fill-underlay-inset", "1.0"),
            ]:
                elem.set(f"{{{INKSTITCH_NS}}}{attr}", val)
        else:
            elem.set(f"{{{INKSTITCH_NS}}}fill_underlay", "false")
            elem.set(f"{{{INKSTITCH_NS}}}fill-underlay", "false")

        # Thread change management
        if fill_color not in processed_colors:
            if not first_color:
                elem.set(f"{{{INKSTITCH_NS}}}thread-change", "true")
            processed_colors.add(fill_color)
            first_color = False

        # Remove stroke to prevent double-stitching
        style_parts = style.split(";") if style else []
        new_style_parts = [p for p in style_parts if p.strip() and not p.strip().startswith("stroke:")]
        new_style_parts.append("stroke:none")
        elem.set("style", ";".join(new_style_parts))

    logger.info(f"embed_thread_colors: processed {processed_count} paths with {len(processed_colors)} unique colors")
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")


# ---------------------------------------------------------------------------
#  Pipeline: SVG upload
# ---------------------------------------------------------------------------

def preprocess_svg_file(
    input_svg_path: str,
    uid,
    width: float = None,
    height: float = None,
    skip_overlap_cleanup: bool = False,
) -> str:
    """
    Full preprocessing pipeline for SVG files:
    1. Inkscape object-to-path (flatten shapes/transforms)
    2. ensure_viewbox (construct viewBox if missing)
    3. bake_transforms (flatten all transforms into absolute path coords)
    4. Flatten SVG DOM (unwrap groups/clipPaths)
    5. Overlap cleanup — skipped when skip_overlap_cleanup=True (e.g. raster
       pipeline where vtracer --hierarchical cutout already handles overlap)
    6. SVG optimization (scour)
    7. Remove empty/trivial paths (Inkscape artifacts)
    8. Canvas resize (fit to hoop)
    9. Embed thread colors + CSS resolution + underlay + compensation

    Args:
        skip_overlap_cleanup: When True, step 5 is bypassed entirely so that
            Bézier curve data is never destroyed by the Shapely boolean ops
            inside cleanup_svg_overlaps().  Use this for raster-sourced SVGs
            where vtracer already emits non-overlapping cutout geometry.
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    base = str(uid)

    flat_svg_path = os.path.join(PROCESSED_DIR, f"{base}_flat.svg")
    cleaned_svg_path = os.path.join(PROCESSED_DIR, f"{base}_cleaned.svg")
    optimized_svg_path = os.path.join(PROCESSED_DIR, f"{base}_optimized.svg")
    final_svg_path = os.path.join(PROCESSED_DIR, f"{base}_inkstitch.svg")

    # 1. Flatten shapes/transforms to paths
    logger.info(f"Flattening shapes/transforms to paths via Inkscape: {input_svg_path}")
    cmd = [
        "xvfb-run", "-a",
        "inkscape",
        input_svg_path,
        "--actions",
        "select-all;object-to-path;page-fit-to-selection;export-plain-svg",
        f"--export-filename={flat_svg_path}"
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        logger.error(f"Inkscape object-to-path flattening failed: {e}. Using raw SVG.")
        shutil.copy(input_svg_path, flat_svg_path)

    # 2. Ensure viewBox exists (construct from width/height if missing)
    ensure_viewbox(flat_svg_path)

    # 3. Bake ALL transforms into absolute path coordinates
    bake_transforms(flat_svg_path)

    # 4. Flatten SVG DOM (unwrap paths, remove clipPaths/groups/nested SVGs)
    flatten_svg_dom(flat_svg_path)

    # 5. Overlap cleanup (stroke-aware) — skipped for raster-sourced SVGs
    if skip_overlap_cleanup:
        logger.info(
            "Skipping overlap cleanup (skip_overlap_cleanup=True): "
            "vtracer --hierarchical cutout already resolved inter-color overlap; "
            "running cleanup_svg_overlaps would destroy Bézier curves."
        )
        shutil.copy(flat_svg_path, cleaned_svg_path)
    else:
        cleanup_svg_overlaps(flat_svg_path, cleaned_svg_path)

    # 6. SVG optimization (scour) — runs BEFORE resize so it can't undo viewBox changes
    shutil.copy(cleaned_svg_path, optimized_svg_path)
    scoured_path = optimized_svg_path + ".scoured.svg"
    optimize_svg(optimized_svg_path, scoured_path)
    shutil.move(scoured_path, optimized_svg_path)

    # 7. Remove empty/trivial paths (Inkscape artifacts)
    remove_empty_paths(optimized_svg_path)

    # 8. Canvas resize — LAST geometry step
    resize_canvas(optimized_svg_path, target_width_mm=width, target_height_mm=height)

    # 9. Embed thread colors (includes CSS resolution)
    shutil.copy(optimized_svg_path, final_svg_path)
    embed_thread_colors(final_svg_path)

    # Cleanup intermediate files
    for path in [flat_svg_path, cleaned_svg_path, optimized_svg_path]:
        if os.path.exists(path):
            os.remove(path)

    return final_svg_path


# ---------------------------------------------------------------------------
#  Pipeline: Raster upload (PNG/JPG)
# ---------------------------------------------------------------------------

def preprocess_to_svg(input_image_path: str, uid, width: float = None, height: float = None) -> str:
    """
    Full preprocessing pipeline for raster images:
    1. Remove background (rembg)
    2. Vectorize (vtracer --hierarchical cutout)
    3. Color quantization (reduce to ≤ MAX_COLORS)
    4. Micro-fragment removal (area check only — Bézier curves NOT touched)
    5. Full SVG preprocessing with skip_overlap_cleanup=True so that the
       destructive Shapely boolean ops are bypassed.  vtracer's cutout mode
       already resolves inter-color overlap at vectorization time.
    """
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    base = str(uid)
    no_bg_path = os.path.join(PROCESSED_DIR, f"{base}_no_bg.png")

    # Lazy imports — only available in Docker container
    from rembg import remove
    from PIL import Image

    # === 1. Remove background ===
    with open(input_image_path, "rb") as inp:
        result = remove(inp.read())
    with open(no_bg_path, "wb") as outp:
        outp.write(result)

    img = Image.open(no_bg_path).convert("RGBA")
    img.save(no_bg_path)

    # === 2. Vectorize with vtracer ===
    temp_svg_path = os.path.join(PROCESSED_DIR, f"{base}_vtracer_temp.svg")
    cmd = [VTRACER_PATH, "--input", no_bg_path, "--output", temp_svg_path]
    for key, value in VTRACER_SETTINGS.items():
        cmd.extend([f"--{key}", str(value)])
    subprocess.run(cmd, check=True)

    # === 2.5 Ensure viewBox (vtracer writes width/height but no viewBox) ===
    ensure_viewbox(temp_svg_path)

    # === 3. Color quantization ===
    quantize_svg_colors(temp_svg_path, MAX_COLORS)

    # === 4. Micro-fragment removal (area check only — curves preserved) ===
    # NOTE: We intentionally do NOT merge same-color paths here. Merging via
    # unary_union + shapely_to_svg_path destroys Bézier curves by converting
    # them to straight-line polygons (L commands only). vtracer --hierarchical
    # cutout already produces non-overlapping geometry so merging is redundant.
    remove_micro_fragments(temp_svg_path, MIN_PATH_AREA)

    # === 5. Full SVG preprocessing — overlap cleanup SKIPPED for raster ===
    # skip_overlap_cleanup=True: cleanup_svg_overlaps() uses Shapely difference()
    # + shapely_to_svg_path() which would destroy all remaining Bézier curves.
    # Inter-color overlap was already resolved by vtracer's cutout mode.
    final_path = preprocess_svg_file(
        temp_svg_path, uid, width, height, skip_overlap_cleanup=True
    )

    # Cleanup
    if os.path.exists(temp_svg_path):
        os.remove(temp_svg_path)
    if os.path.exists(no_bg_path):
        os.remove(no_bg_path)

    return final_path
