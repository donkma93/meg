# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - VECTOR ICON FACTORY
Tạo vector icon mượt mà, sắc nét anti-aliased chất lượng cao (High-DPI).
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
        cx, cy = cw // 2, ch // 2

        if name == "play":
            poly = [
                (int(cw * 0.32), int(ch * 0.22)),
                (int(cw * 0.78), int(ch * 0.5)),
                (int(cw * 0.32), int(ch * 0.78))
            ]
            d.polygon(poly, fill=color)

        elif name == "stop":
            d.rounded_rectangle(
                [int(cw * 0.26), int(ch * 0.26), int(cw * 0.74), int(ch * 0.74)],
                radius=int(2 * scale),
                fill=color
            )

        elif name in ("gear", "settings"):
            r_out = int(cw * 0.38)
            r_in = int(cw * 0.25)
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

        elif name == "refresh":
            d.arc([int(cw * 0.2), int(ch * 0.2), int(cw * 0.8), int(ch * 0.8)], start=40, end=310, fill=color, width=lw)
            arrow = [
                (int(cw * 0.76), int(ch * 0.34)),
                (int(cw * 0.92), int(ch * 0.18)),
                (int(cw * 0.66), int(ch * 0.16))
            ]
            d.polygon(arrow, fill=color)

        elif name == "plus":
            hl = int(cw * 0.28)
            d.line([(cx, cy - hl), (cx, cy + hl)], fill=color, width=int(1.8 * scale))
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))

        elif name == "minus":
            hl = int(cw * 0.28)
            d.line([(cx - hl, cy), (cx + hl, cy)], fill=color, width=int(1.8 * scale))

        elif name == "trash":
            d.rounded_rectangle([int(cw * 0.26), int(ch * 0.35), int(cw * 0.74), int(ch * 0.85)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.20), int(ch * 0.28)), (int(cw * 0.80), int(ch * 0.28))], fill=color, width=lw)
            d.line([(int(cw * 0.40), int(ch * 0.20)), (int(cw * 0.60), int(ch * 0.20))], fill=color, width=lw)
            d.line([(int(cw * 0.42), int(ch * 0.42)), (int(cw * 0.42), int(ch * 0.76))], fill=color, width=lw)
            d.line([(int(cw * 0.58), int(ch * 0.42)), (int(cw * 0.58), int(ch * 0.76))], fill=color, width=lw)

        elif name == "clock":
            r = int(cw * 0.36)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=lw)
            d.line([(cx, cy), (cx, cy - int(r * 0.6))], fill=color, width=lw)
            d.line([(cx, cy), (cx + int(r * 0.45), cy)], fill=color, width=lw)

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

        elif name == "chevron_down":
            hw = int(cw * 0.22)
            hh = int(ch * 0.14)
            d.line([(cx - hw, cy - hh), (cx, cy + hh)], fill=color, width=lw)
            d.line([(cx, cy + hh), (cx + hw, cy - hh)], fill=color, width=lw)

        elif name == "chevron_up":
            hw = int(cw * 0.22)
            hh = int(ch * 0.14)
            d.line([(cx - hw, cy + hh), (cx, cy - hh)], fill=color, width=lw)
            d.line([(cx, cy - hh), (cx + hw, cy + hh)], fill=color, width=lw)

        elif name == "check":
            d.line([(int(cw * 0.22), int(ch * 0.50)), (int(cw * 0.42), int(ch * 0.72))], fill=color, width=lw)
            d.line([(int(cw * 0.42), int(ch * 0.72)), (int(cw * 0.80), int(ch * 0.28))], fill=color, width=lw)

        elif name in ("close", "x"):
            hl = int(cw * 0.24)
            d.line([(cx - hl, cy - hl), (cx + hl, cy + hl)], fill=color, width=lw)
            d.line([(cx + hl, cy - hl), (cx - hl, cy + hl)], fill=color, width=lw)

        elif name in ("users", "team"):
            # Multi-user silhouette
            d.ellipse([int(cw * 0.20), int(ch * 0.18), int(cw * 0.46), int(ch * 0.44)], fill=color)
            d.arc([int(cw * 0.08), int(ch * 0.46), int(cw * 0.58), int(ch * 0.88)], 180, 0, fill=color, width=lw)
            d.ellipse([int(cw * 0.54), int(ch * 0.22), int(cw * 0.78), int(ch * 0.46)], fill=color)
            d.arc([int(cw * 0.46), int(ch * 0.48), int(cw * 0.88), int(ch * 0.88)], 180, 0, fill=color, width=lw)

        elif name == "user":
            # Single user silhouette
            d.ellipse([int(cw * 0.34), int(ch * 0.18), int(cw * 0.66), int(ch * 0.50)], fill=color)
            d.arc([int(cw * 0.20), int(ch * 0.52), int(cw * 0.80), int(ch * 0.90)], 180, 0, fill=color, width=lw)

        elif name == "link":
            # Chain links
            r = int(cw * 0.13)
            d.rounded_rectangle([int(cw * 0.14), int(ch * 0.35), int(cw * 0.54), int(ch * 0.65)], radius=r, outline=color, width=lw)
            d.rounded_rectangle([int(cw * 0.46), int(ch * 0.35), int(cw * 0.86), int(ch * 0.65)], radius=r, outline=color, width=lw)

        elif name in ("grid", "window", "layout"):
            # 2x2 grid windows
            gr = max(1, int(1.5 * scale))
            d.rounded_rectangle([int(cw * 0.18), int(ch * 0.18), int(cw * 0.46), int(ch * 0.46)], radius=gr, fill=color)
            d.rounded_rectangle([int(cw * 0.54), int(ch * 0.18), int(cw * 0.82), int(ch * 0.46)], radius=gr, fill=color)
            d.rounded_rectangle([int(cw * 0.18), int(ch * 0.54), int(cw * 0.46), int(ch * 0.82)], radius=gr, fill=color)
            d.rounded_rectangle([int(cw * 0.54), int(ch * 0.54), int(cw * 0.82), int(ch * 0.82)], radius=gr, fill=color)

        elif name in ("gem", "diamond"):
            # Faceted gem
            poly_gem = [
                (int(cw * 0.28), int(ch * 0.20)),
                (int(cw * 0.72), int(ch * 0.20)),
                (int(cw * 0.88), int(ch * 0.46)),
                (int(cw * 0.50), int(ch * 0.86)),
                (int(cw * 0.12), int(ch * 0.46))
            ]
            d.polygon(poly_gem, outline=color, fill=color)

        elif name in ("fire", "flame"):
            # Flame
            poly_fire = [
                (int(cw * 0.50), int(ch * 0.12)),
                (int(cw * 0.68), int(ch * 0.34)),
                (int(cw * 0.82), int(ch * 0.56)),
                (int(cw * 0.74), int(ch * 0.84)),
                (int(cw * 0.50), int(ch * 0.88)),
                (int(cw * 0.26), int(ch * 0.84)),
                (int(cw * 0.18), int(ch * 0.56)),
                (int(cw * 0.36), int(ch * 0.38))
            ]
            d.polygon(poly_fire, fill=color)

        elif name in ("party", "handshake"):
            # Party / Handshake
            d.line([(int(cw * 0.16), int(ch * 0.54)), (int(cw * 0.42), int(ch * 0.34))], fill=color, width=lw)
            d.line([(int(cw * 0.42), int(ch * 0.34)), (int(cw * 0.58), int(ch * 0.50))], fill=color, width=lw)
            d.line([(int(cw * 0.58), int(ch * 0.50)), (int(cw * 0.84), int(ch * 0.30))], fill=color, width=lw)
            d.line([(int(cw * 0.42), int(ch * 0.50)), (int(cw * 0.58), int(ch * 0.66))], fill=color, width=lw)
            d.line([(int(cw * 0.58), int(ch * 0.66)), (int(cw * 0.84), int(ch * 0.46))], fill=color, width=lw)

        elif name in ("telegram", "paper_plane"):
            poly_tg = [
                (int(cw * 0.14), int(ch * 0.52)),
                (int(cw * 0.86), int(ch * 0.16)),
                (int(cw * 0.62), int(ch * 0.84)),
                (int(cw * 0.48), int(ch * 0.62))
            ]
            d.polygon(poly_tg, fill=color)
            d.line([(int(cw * 0.48), int(ch * 0.62)), (int(cw * 0.86), int(ch * 0.16))], fill="#ffffff", width=max(1, lw // 2))

        elif name in ("import", "download"):
            # Arrow down into tray
            d.line([(cx, int(ch * 0.16)), (cx, int(ch * 0.60))], fill=color, width=lw)
            arrow = [
                (int(cw * 0.34), int(ch * 0.48)),
                (int(cw * 0.66), int(ch * 0.48)),
                (cx, int(ch * 0.68))
            ]
            d.polygon(arrow, fill=color)
            d.line([(int(cw * 0.20), int(ch * 0.54)), (int(cw * 0.20), int(ch * 0.82)), (int(cw * 0.80), int(ch * 0.82)), (int(cw * 0.80), int(ch * 0.54))], fill=color, width=lw)

        elif name == "terminal":
            d.line([(int(cw * 0.22), int(ch * 0.28)), (int(cw * 0.46), int(ch * 0.50))], fill=color, width=lw)
            d.line([(int(cw * 0.46), int(ch * 0.50)), (int(cw * 0.22), int(ch * 0.72))], fill=color, width=lw)
            d.line([(int(cw * 0.54), int(ch * 0.72)), (int(cw * 0.82), int(ch * 0.72))], fill=color, width=lw)

        elif name in ("map", "pin"):
            # Map location pin
            d.ellipse([int(cw * 0.28), int(ch * 0.14), int(cw * 0.72), int(ch * 0.58)], outline=color, width=lw)
            d.ellipse([int(cw * 0.44), int(ch * 0.30), int(cw * 0.56), int(ch * 0.42)], fill=color)
            d.polygon([(int(cw * 0.32), int(ch * 0.50)), (int(cw * 0.68), int(ch * 0.50)), (cx, int(ch * 0.86))], fill=color)

        elif name in ("target", "crosshair"):
            cr = int(cw * 0.32)
            d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline=color, width=lw)
            d.line([(cx, cy - cr - int(cw * 0.08)), (cx, cy + cr + int(cw * 0.08))], fill=color, width=lw)
            d.line([(cx - cr - int(cw * 0.08), cy), (cx + cr + int(cw * 0.08), cy)], fill=color, width=lw)

        elif name in ("star", "level"):
            pts = []
            for i in range(10):
                r_curr = int(cw * 0.38) if i % 2 == 0 else int(cw * 0.18)
                ang = -math.pi / 2 + i * (math.pi / 5)
                pts.append((cx + int(r_curr * math.cos(ang)), cy + int(r_curr * math.sin(ang))))
            d.polygon(pts, fill=color)

        elif name == "key":
            d.ellipse([int(cw * 0.20), int(ch * 0.20), int(cw * 0.52), int(ch * 0.52)], outline=color, width=lw)
            d.line([(int(cw * 0.46), int(ch * 0.46)), (int(cw * 0.82), int(ch * 0.82))], fill=color, width=lw)
            d.line([(int(cw * 0.72), int(ch * 0.72)), (int(cw * 0.82), int(ch * 0.62))], fill=color, width=lw)
            d.line([(int(cw * 0.62), int(ch * 0.62)), (int(cw * 0.72), int(ch * 0.52))], fill=color, width=lw)

        elif name == "shield":
            poly_shield = [
                (int(cw * 0.22), int(ch * 0.20)),
                (int(cw * 0.78), int(ch * 0.20)),
                (int(cw * 0.78), int(ch * 0.54)),
                (cx, int(ch * 0.84)),
                (int(cw * 0.22), int(ch * 0.54))
            ]
            d.polygon(poly_shield, outline=color, width=lw)

        elif name == "sword":
            d.line([(int(cw * 0.20), int(ch * 0.80)), (int(cw * 0.74), int(ch * 0.26))], fill=color, width=lw)
            d.line([(int(cw * 0.28), int(ch * 0.64)), (int(cw * 0.44), int(ch * 0.80))], fill=color, width=lw)
            d.ellipse([int(cw * 0.16), int(ch * 0.76), int(cw * 0.26), int(ch * 0.86)], fill=color)

        elif name == "eye":
            d.arc([int(cw * 0.16), int(ch * 0.24), int(cw * 0.84), int(ch * 0.76)], 200, 340, fill=color, width=lw)
            d.arc([int(cw * 0.16), int(ch * 0.24), int(cw * 0.84), int(ch * 0.76)], 20, 160, fill=color, width=lw)
            d.ellipse([cx - int(cw * 0.12), cy - int(ch * 0.12), cx + int(cw * 0.12), cy + int(ch * 0.12)], fill=color)

        else:
            # Default dot
            r = int(cw * 0.25)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

        img_smooth = im.resize(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=img_smooth, dark_image=img_smooth, size=size)
        cls._cache[key] = ctk_img
        return ctk_img
