import colorsys
import io
import math
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image

HEX_COLOR_REGEX = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Converts RGB integers (0-255) to uppercase hex string."""
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def hex_to_rgb(hex_code: str) -> Tuple[int, int, int]:
    """Converts hex code to RGB integers (0-255)."""
    hex_clean = hex_code.lstrip('#')
    if len(hex_clean) == 3:
        hex_clean = ''.join(c * 2 for c in hex_clean)
    return int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)


def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Converts RGB (0-255) to HSL: H in [0, 360], S in [0, 1], L in [0, 1]."""
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0, s, l


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Converts HSL (H in [0, 360], S in [0, 1], L in [0, 1]) to hex string."""
    h_norm = (h % 360.0) / 360.0
    s_clamped = max(0.0, min(1.0, s))
    l_clamped = max(0.0, min(1.0, l))
    r, g, b = colorsys.hls_to_rgb(h_norm, l_clamped, s_clamped)
    return rgb_to_hex(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def get_relative_luminance(r: int, g: int, b: int) -> float:
    """Calculates relative luminance according to WCAG 2.1 specifications."""
    def channel_lum(val: float) -> float:
        v = val / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)

    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def get_contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculates WCAG contrast ratio between two hex colors."""
    lum1 = get_relative_luminance(*hex_to_rgb(hex1))
    lum2 = get_relative_luminance(*hex_to_rgb(hex2))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_accessible_primary(h: float, s: float, l: float) -> str:
    """
    Ensures primary brand color has sufficient contrast when used as a button background
    with white text (contrast >= 4.5:1 against white according to WCAG 2.1 AA).
    """
    target_l = min(l, 0.42)
    target_s = max(s, 0.40)
    candidate = hsl_to_hex(h, target_s, target_l)
    while get_contrast_ratio(candidate, "#FFFFFF") < 4.5 and target_l > 0.12:
        target_l -= 0.02
        candidate = hsl_to_hex(h, target_s, target_l)
    return candidate


class OrganizationBrandingService:
    """
    Deterministic image color extraction and accessible theme palette generation.
    Supports transparent, monochrome, multi-color, light, and dark logos.
    """

    @classmethod
    def validate_hex_color(cls, value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        return bool(HEX_COLOR_REGEX.match(value.strip()))

    @classmethod
    def extract_dominant_colors(cls, image_bytes_or_file, max_colors: int = 5) -> List[str]:
        """
        Deterministically extracts dominant non-background colors from an image.
        Filters transparent, near-white, and near-black pixels.
        """
        try:
            if hasattr(image_bytes_or_file, 'read'):
                image_bytes_or_file.seek(0)
                img = Image.open(image_bytes_or_file)
            else:
                img = Image.open(io.BytesIO(image_bytes_or_file))
        except Exception:
            return ["#166534"]

        img = img.convert('RGBA')
        img.thumbnail((120, 120), Image.Resampling.LANCZOS)

        pixels = list(img.getdata())
        color_counts: Dict[Tuple[int, int, int], int] = {}
        total_valid = 0

        for r, g, b, a in pixels:
            # Filter out transparent pixels
            if a < 40:
                continue

            # Quantize color slightly to group similar shades (step of 12)
            qr = (r // 12) * 12
            qg = (g // 12) * 12
            qb = (b // 12) * 12

            # Check if pure white or pure black background
            is_near_white = (qr > 240 and qg > 240 and qb > 240)
            is_near_black = (qr < 18 and qg < 18 and qb < 18)

            if is_near_white or is_near_black:
                continue

            color_counts[(qr, qg, qb)] = color_counts.get((qr, qg, qb), 0) + 1
            total_valid += 1

        # If image was completely monochrome / near-white / near-black
        if not color_counts or total_valid < 10:
            # Check if image has dark shapes on transparent background
            dark_pixels = sum(1 for r, g, b, a in pixels if a >= 40 and r < 50 and g < 50 and b < 50)
            if dark_pixels > 20:
                return ["#0F172A", "#1E293B"]
            return ["#166534"]

        # Sort by frequency
        sorted_colors = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)

        # Select distinct dominant colors (hue difference >= 20° or lightness delta >= 0.20)
        dominant: List[str] = []
        for (r, g, b), count in sorted_colors:
            hex_c = rgb_to_hex(r, g, b)
            h, s, l = rgb_to_hsl(r, g, b)
            
            # Check distinctness against already chosen colors
            is_distinct = True
            for chosen in dominant:
                cr, cg, cb = hex_to_rgb(chosen)
                ch, cs, cl = rgb_to_hsl(cr, cg, cb)
                h_diff = min(abs(h - ch), 360 - abs(h - ch))
                l_diff = abs(l - cl)
                if h_diff < 22 and l_diff < 0.22:
                    is_distinct = False
                    break

            if is_distinct:
                dominant.append(hex_c)
                if len(dominant) >= max_colors:
                    break

        return dominant if dominant else ["#166534"]

    @classmethod
    def generate_coordinated_palettes(cls, base_hex: str) -> List[Dict]:
        """
        Generates 3 coordinated, WCAG-tested color palettes from a base brand color:
        1. Vibrant Brand (primary dominant, energetic accent)
        2. Modern Professional (refined saturation, balanced slate)
        3. Deep Focus (rich deep tone, crisp high-contrast interactive elements)
        """
        if not cls.validate_hex_color(base_hex):
            base_hex = "#166534"

        r, g, b = hex_to_rgb(base_hex)
        h, s, l = rgb_to_hsl(r, g, b)

        # Handle monochrome / grayscale input gracefully
        if s < 0.12:
            h = 142.0  # Default to clean emerald/green hue
            s = 0.65
            l = 0.32

        # -------------------------------------------------------------
        # Palette 1: Brand Vibrant
        # -------------------------------------------------------------
        p1_primary = ensure_accessible_primary(h, s, l)
        p1_secondary = hsl_to_hex(h + 25.0, min(1.0, s * 0.9), 0.38)
        p1_accent = hsl_to_hex(h + 45.0, min(1.0, s * 0.95), 0.55)
        p1_sidebar_bg = hsl_to_hex(h, 0.18, 0.97)

        # -------------------------------------------------------------
        # Palette 2: Modern Professional
        # -------------------------------------------------------------
        p2_primary = ensure_accessible_primary(h, max(0.40, s * 0.70), 0.34)
        p2_secondary = hsl_to_hex(h - 20.0, max(0.35, s * 0.65), 0.42)
        p2_accent = hsl_to_hex(h + 30.0, 0.75, 0.50)
        p2_sidebar_bg = "#F8FAFC"

        # -------------------------------------------------------------
        # Palette 3: Deep Focus
        # -------------------------------------------------------------
        p3_primary = ensure_accessible_primary(h, max(0.55, s * 0.85), 0.22)
        p3_secondary = hsl_to_hex(h + 15.0, 0.80, 0.48)
        p3_accent = hsl_to_hex(h, 0.85, 0.60)
        p3_sidebar_bg = hsl_to_hex(h, 0.30, 0.14)

        return [
            {
                "id": "vibrant",
                "name": "Brand Vibrant",
                "description": "Lively and bold, highlighting your extracted dominant brand identity.",
                "primary_color": p1_primary,
                "secondary_color": p1_secondary,
                "accent_color": p1_accent,
                "sidebar_bg_color": p1_sidebar_bg,
            },
            {
                "id": "professional",
                "name": "Modern Professional",
                "description": "Balanced, refined tones optimized for enterprise readability.",
                "primary_color": p2_primary,
                "secondary_color": p2_secondary,
                "accent_color": p2_accent,
                "sidebar_bg_color": p2_sidebar_bg,
            },
            {
                "id": "deep",
                "name": "Deep Focus",
                "description": "Rich deep primary shade paired with crisp, high-contrast interactive elements.",
                "primary_color": p3_primary,
                "secondary_color": p3_secondary,
                "accent_color": p3_accent,
                "sidebar_bg_color": p3_sidebar_bg,
            },
        ]
