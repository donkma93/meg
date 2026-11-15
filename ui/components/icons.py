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
        elif name == "trash":
            # Thùng rác
            d.rounded_rectangle([int(cw * 0.26), int(ch * 0.35), int(cw * 0.74), int(ch * 0.85)], radius=int(2 * scale), outline=color, width=lw)
            d.line([(int(cw * 0.20), int(ch * 0.28)), (int(cw * 0.80), int(ch * 0.28))], fill=color, width=lw)
            d.line([(int(cw * 0.40), int(ch * 0.20)), (int(cw * 0.60), int(ch * 0.20))], fill=color, width=lw)
            d.line([(int(cw * 0.42), int(ch * 0.42)), (int(cw * 0.42), int(ch * 0.76))], fill=color, width=lw)
            d.line([(int(cw * 0.58), int(ch * 0.42)), (int(cw * 0.58), int(ch * 0.76))], fill=color, width=lw)
        elif name == "clock":
            cx, cy = cw // 2, ch // 2
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
            cx, cy = cw // 2, ch // 2
            hw = int(cw * 0.22)
            hh = int(ch * 0.14)
            d.line([(cx - hw, cy - hh), (cx, cy + hh)], fill=color, width=lw)
            d.line([(cx, cy + hh), (cx + hw, cy - hh)], fill=color, width=lw)
        else:
            # Default dot
            cx, cy = cw // 2, ch // 2
            r = int(cw * 0.25)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

        img_smooth = im.resize(size, Image.Resampling.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=img_smooth, dark_image=img_smooth, size=size)
        cls._cache[key] = ctk_img
        return ctk_img
