from PIL import Image
import numpy as np
from sklearn.cluster import KMeans
from app.pipeline.config import MAX_COLORS

def rgb_to_lab(rgb):
    """Convert RGB to LAB color space for better perceptual color difference measurement"""
    r, g, b = rgb
    
    # Normalize RGB values
    r = r / 255.0
    g = g / 255.0
    b = b / 255.0
    
    # Convert to XYZ
    if r > 0.04045:
        r = ((r + 0.055) / 1.055) ** 2.4
    else:
        r = r / 12.92
    if g > 0.04045:
        g = ((g + 0.055) / 1.055) ** 2.4
    else:
        g = g / 12.92
    if b > 0.04045:
        b = ((b + 0.055) / 1.055) ** 2.4
    else:
        b = b / 12.92

    r *= 100.0
    g *= 100.0
    b *= 100.0

    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    # Convert XYZ to Lab
    x /= 95.047
    y /= 100.000
    z /= 108.883

    if x > 0.008856:
        x = x ** (1/3)
    else:
        x = (7.787 * x) + (16 / 116)
    if y > 0.008856:
        y = y ** (1/3)
    else:
        y = (7.787 * y) + (16 / 116)
    if z > 0.008856:
        z = z ** (1/3)
    else:
        z = (7.787 * z) + (16 / 116)

    L = (116 * y) - 16
    a = 500 * (x - y)
    b = 200 * (y - z)

    return L, a, b

def get_dominant_colors(path, tolerance=5):
    """
    Get the dominant colors in the image using k-means clustering.
    Converts to LAB color space for better perceptual grouping.
    """
    # Open and convert image to RGB
    img = Image.open(path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Convert to numpy array
    pixels = np.float32(img).reshape(-1, 3)
    
    # Convert pixels to LAB color space
    lab_pixels = np.array([rgb_to_lab(pixel) for pixel in pixels])
    
    # Determine number of clusters (colors)
    n_colors = min(len(np.unique(pixels, axis=0)), MAX_COLORS)
    if n_colors < 2:
        n_colors = 2
    
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=n_colors, random_state=42)
    labels = kmeans.fit_predict(lab_pixels)
    
    # Get the counts of each cluster
    unique_labels, counts = np.unique(labels, return_counts=True)
    
    # Get the RGB values for each cluster center
    centers = kmeans.cluster_centers_
    colors = []
    
    # Sort colors by frequency (most common first)
    sorted_indices = np.argsort(counts)[::-1]
    
    for idx in sorted_indices:
        count = counts[idx]
        # Only include colors that make up more than 1% of the image
        if count / len(labels) > 0.01:
            colors.append(tuple(np.round(pixels[labels == idx].mean(axis=0)).astype(int)))
    
    return colors

def count_real_colors(path):
    """
    Count the actual number of distinct colors in the image,
    grouping similar colors together.
    """
    colors = get_dominant_colors(path)
    return len(colors)