"""
Constants for MEGAMU Auto Train Dashboard.
"""

from pathlib import Path
import sys

def get_resource_path(name: str) -> Path:
    base = Path(__file__).resolve().parent.parent
    p = base / name
    if p.exists():
        return p
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / name).exists():
        return Path(meipass) / name
    return p

LOGO_FILE = get_resource_path("megamu_dashboard_logo.png")
ICON_FILE = get_resource_path("megamu_dashboard_icon.ico")

APP_NAME = "MEGAMU Auto Train Dashboard"
APP_VERSION = "v1.5.7"

CLASS_ID_TO_CODE = {
    0: "DW", 1: "DK", 2: "FE", 3: "MG", 4: "DL", 5: "SU", 6: "RF", 7: "GL",
    8: "RW", 9: "SL", 10: "GC", 11: "KM", 12: "LM", 13: "IK", 14: "AL", 15: "CR"
}

CLASS_CODE_TO_NAME = {
    "DW": "Dark Wizard (Phù Thủy)",
    "DK": "Dark Knight (Chiến Binh)",
    "FE": "Fairy Elf (Tiên Nữ)",
    "MG": "Magic Gladiator (Đấu Sĩ)",
    "DL": "Dark Lord (Chúa Tể)",
    "SU": "Summoner (Thuật Sĩ)",
    "RF": "Rage Fighter (Thiết Binh)",
    "GL": "Grow Lancer (Thương Thủ)",
    "RW": "Rune Wizard (Phù Thủy Rune)",
    "SL": "Slayer (Sát Thủ)",
    "GC": "Gun Crusher (Pháo Thủ)",
    "KM": "Kundun Mephis",
    "LM": "Lemuria",
    "IK": "Illusion Knight (Huyễn Ảnh)",
    "AL": "Alchemist (Giả Kim)",
    "CR": "Crusher"
}

PROFILE_NAMES = [f"Config {i}" for i in range(1, 11)]
MAX_SLOTS = 10

