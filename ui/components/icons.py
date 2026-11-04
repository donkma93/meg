"""
High-DPI Vector Icon Factory for MEGAMU Auto Train Dashboard.
Generates smooth anti-aliased vector icons using PIL and caches them into CTkImage.
"""

import math
from typing import Dict, Tuple
from PIL import Image, ImageDraw
import customtkinter as ctk


class UiIconFactory:
    """Tạo vector icon mượt mà sắc nét anti-aliased chất lượng cao (High-DPI)."""
    _cache: Dict[Tuple[str, str, Tuple[int, int]], ctk.CTkImage] = {}

    @classmethod
    def get(cls, name: str, color: str = "#cbd5e1", size: Tuple[int, int] = (16, 16)) -> ctk.CTkImage:
        key = (name, color, size)
        if key in cls._cache:
            return cls._cache[key]

        scale = 4
        cw = size[0] * scale
        ch = size[1] * scale
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        lw = max(2, int(1.4 * scale))
        pad = int(2.5 * scale)

        if name == "play":
            poly = [(int(cw * 0.32), int(ch * 0.22)), (int(cw * 0.78), int(ch * 0.5)), (int(cw * 0.32), int(ch * 0.78))]
            d.polygon(poly, fill=color)
        elif name == "stop":
            d.rounded_rectangle([int(cw * 0.26), int(ch * 0.26), int(cw * 0.74), int(ch * 0.74)], radius=int(2 * scale), fill=color)
        elif name == "gear":
            r_out = int(cw * 0.38)
            r_in = int(cw * 0.25)
            cx, cy = cw // 2, ch // 2
            d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=color, width=lw)
            teeth = 8
            for i in range(teeth):
                ang = i * (2 * math.pi / teeth)
                x1 = cx + int(r_in * math.cos(ang))
                y1 = cy + int(r_in * math.sin(ang))
                x2 = cx + int(r_out * math.cos(ang))
                y2 = cy + int(r_out * math.sin(ang))
                d.line([(x1, y1), (x2, y2)], fill=color, width=lw)
            hub_r = max(2, int(cw * 0.08))
            d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=color)
        elif name == "file":
            d.rounded_rectangle([int(cw * 0.24), int(ch * 0.15), int(cw * 0.76), int(ch * 0.85)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.36)), (int(cw * 0.64), int(ch * 0.36))], fill=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.50)), (int(cw * 0.64), int(ch * 0.50))], fill=color, width=lw)
            d.line([(int(cw * 0.36), int(ch * 0.64)), (int(cw * 0.52), int(ch * 0.64))], fill=color, width=lw)
        elif name == "user":
            cx, cy = cw // 2, ch // 2
            hr = int(cw * 0.18)
            d.ellipse([cx - hr, int(ch * 0.14), cx + hr, int(ch * 0.14) + 2 * hr], fill=color)
            d.pieslice([int(cw * 0.18), int(ch * 0.46), int(cw * 0.82), int(ch * 1.10)], start=180, end=360, fill=color)
        elif name == "link":
            lw_link = max(2, int(1.4 * scale))
            d.rounded_rectangle([int(cw * 0.16), int(ch * 0.32), int(cw * 0.56), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw_link)
            d.rounded_rectangle([int(cw * 0.44), int(ch * 0.32), int(cw * 0.84), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw_link)
        elif name == "refresh":
            d.arc([int(cw * 0.2), int(ch * 0.2), int(cw * 0.8), int(ch * 0.8)], start=40, end=310, fill=color, width=lw)
            arrow = [(int(cw * 0.76), int(ch * 0.34)), (int(cw * 0.92), int(ch * 0.18)), (int(cw * 0.66), int(ch * 0.16))]
            d.polygon(arrow, fill=color)
        elif name == "plus":
            cx, cy = cw // 2, ch // 2
            hl = int(cw * 0.28)
            d.line([(cx, cy - hl), (cx, cy + hl)], fill=color, width=int(1.8 * scale))
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))
        elif name == "minus":
            cx, cy = cw // 2, ch // 2
            hl = int(cw * 0.28)
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))
        elif name == "chat":
            d.rounded_rectangle([int(cw * 0.18), int(ch * 0.20), int(cw * 0.82), int(ch * 0.68)], radius=int(3 * scale), outline=color, width=lw)
            poly = [(int(cw * 0.32), int(ch * 0.68)), (int(cw * 0.46), int(ch * 0.68)), (int(cw * 0.24), int(ch * 0.85))]
            d.polygon(poly, fill=color)
        elif name == "chevron_down":
            cx, cy = cw // 2, ch // 2
            hw = int(cw * 0.22)
            hh = int(ch * 0.14)
            d.line([(cx - hw, cy - hh), (cx, cy + hh)], fill=color, width=lw)
            d.line([(cx, cy + hh), (cx + hw, cy - hh)], fill=color, width=lw)
        elif name == "dot":
            cx, cy = cw // 2, ch // 2
            r = int(cw * 0.35)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        elif name in ("bolt", "zap"):
            poly = [
                (int(cw * 0.54), int(ch * 0.12)),
                (int(cw * 0.22), int(ch * 0.52)),
                (int(cw * 0.48), int(ch * 0.52)),
                (int(cw * 0.42), int(ch * 0.88)),
                (int(cw * 0.78), int(ch * 0.44)),
                (int(cw * 0.52), int(ch * 0.44))
            ]
            d.polygon(poly, fill=color)
        elif name in ("fire", "flame"):
            poly = [
                (int(cw * 0.50), int(ch * 0.10)),
                (int(cw * 0.65), int(ch * 0.28)),
                (int(cw * 0.82), int(ch * 0.52)),
                (int(cw * 0.80), int(ch * 0.76)),
                (int(cw * 0.62), int(ch * 0.92)),
                (int(cw * 0.38), int(ch * 0.92)),
                (int(cw * 0.20), int(ch * 0.76)),
                (int(cw * 0.18), int(ch * 0.52)),
                (int(cw * 0.35), int(ch * 0.28)),
                (int(cw * 0.44), int(ch * 0.42)),
            ]
            d.polygon(poly, fill=color)
        elif name in ("gem", "diamond"):
            poly = [
                (int(cw * 0.28), int(ch * 0.20)),
                (int(cw * 0.72), int(ch * 0.20)),
                (int(cw * 0.90), int(ch * 0.46)),
                (int(cw * 0.50), int(ch * 0.88)),
                (int(cw * 0.10), int(ch * 0.46))
            ]
            d.polygon(poly, fill=color)
            d.line([(int(cw * 0.28), int(ch * 0.20)), (int(cw * 0.50), int(ch * 0.88))], fill=color, width=lw)
            d.line([(int(cw * 0.72), int(ch * 0.20)), (int(cw * 0.50), int(ch * 0.88))], fill=color, width=lw)
            d.line([(int(cw * 0.10), int(ch * 0.46)), (int(cw * 0.90), int(ch * 0.46))], fill=color, width=lw)
        elif name in ("users", "team"):
            hr1 = int(cw * 0.13)
            d.ellipse([int(cw * 0.65) - hr1, int(ch * 0.16), int(cw * 0.65) + hr1, int(ch * 0.16) + 2 * hr1], fill=color)
            d.pieslice([int(cw * 0.45), int(ch * 0.46), int(cw * 0.85), int(ch * 0.96)], start=180, end=360, fill=color)
            hr2 = int(cw * 0.15)
            d.ellipse([int(cw * 0.35) - hr2, int(ch * 0.20), int(cw * 0.35) + hr2, int(ch * 0.20) + 2 * hr2], fill=color)
            d.pieslice([int(cw * 0.12), int(ch * 0.52), int(cw * 0.58), int(ch * 1.05)], start=180, end=360, fill=color)
        elif name in ("dice", "gift", "game"):
            d.rounded_rectangle([int(cw * 0.20), int(ch * 0.20), int(cw * 0.80), int(ch * 0.80)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.50), int(ch * 0.20)), (int(cw * 0.50), int(ch * 0.80))], fill=color, width=lw)
            d.line([(int(cw * 0.20), int(ch * 0.50)), (int(cw * 0.80), int(ch * 0.50))], fill=color, width=lw)
        elif name in ("mirror", "sparkle", "shield"):
            poly = [
                (int(cw * 0.50), int(ch * 0.15)),
                (int(cw * 0.80), int(ch * 0.25)),
                (int(cw * 0.80), int(ch * 0.55)),
                (int(cw * 0.50), int(ch * 0.85)),
                (int(cw * 0.20), int(ch * 0.55)),
                (int(cw * 0.20), int(ch * 0.25))
            ]
            d.polygon(poly, outline=color, width=lw)
        elif name in ("update", "download"):
            cx = cw // 2
            d.line([(int(cw * 0.20), int(ch * 0.68)), (int(cw * 0.20), int(ch * 0.84)), (int(cw * 0.80), int(ch * 0.84)), (int(cw * 0.80), int(ch * 0.68))], fill=color, width=lw)
            d.line([(cx, int(ch * 0.14)), (cx, int(ch * 0.58))], fill=color, width=int(1.8 * scale))
            arrow = [(cx - int(cw * 0.22), int(ch * 0.44)), (cx + int(cw * 0.22), int(ch * 0.44)), (cx, int(ch * 0.66))]
            d.polygon(arrow, fill=color)
        elif name in ("key", "lock", "license"):
            cx = cw // 2
            r_out = int(cw * 0.22)
            d.ellipse([cx - r_out, int(ch * 0.12), cx + r_out, int(ch * 0.12) + 2 * r_out], fill=color)
            r_in = int(cw * 0.10)
            d.ellipse([cx - r_in, int(ch * 0.12) + r_out - r_in, cx + r_in, int(ch * 0.12) + r_out + r_in], fill=(0, 0, 0, 0))
            stem_w = int(1.8 * scale)
            d.rectangle([cx - stem_w // 2, int(ch * 0.12) + 2 * r_out, cx + stem_w // 2, int(ch * 0.88)], fill=color)
            d.rectangle([cx, int(ch * 0.65), cx + int(cw * 0.22), int(ch * 0.73)], fill=color)
            d.rectangle([cx, int(ch * 0.78), cx + int(cw * 0.18), int(ch * 0.86)], fill=color)
        elif name in ("pin", "location", "marker"):
            cx, cy = cw // 2, int(ch * 0.38)
            r = int(cw * 0.26)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
            poly = [(cx - r, cy), (cx + r, cy), (cx, int(ch * 0.88))]
            d.polygon(poly, fill=color)
            inner_r = int(r * 0.42)
            d.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill="#181c26")
        elif name in ("door", "enter", "login"):
            d.rounded_rectangle([int(cw * 0.35), int(ch * 0.15), int(cw * 0.85), int(ch * 0.85)], radius=int(2 * scale), outline=color, width=lw)
            d.ellipse([int(cw * 0.45), int(ch * 0.48), int(cw * 0.52), int(ch * 0.55)], fill=color)
            d.line([(int(cw * 0.12), int(ch * 0.50)), (int(cw * 0.52), int(ch * 0.50))], fill=color, width=lw)
            arrow = [(int(cw * 0.40), int(ch * 0.36)), (int(cw * 0.56), int(ch * 0.50)), (int(cw * 0.40), int(ch * 0.64))]
            d.polygon(arrow, fill=color)
        elif name in ("ticket", "coupon", "pass"):
            d.rounded_rectangle([int(cw * 0.14), int(ch * 0.24), int(cw * 0.86), int(ch * 0.76)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.48), int(ch * 0.32)), (int(cw * 0.48), int(ch * 0.68))], fill=color, width=max(1, int(1 * scale)))

        res_img = im.resize(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=res_img, dark_image=res_img, size=size)
        cls._cache[key] = ctk_img
        return ctk_img

