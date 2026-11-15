# -*- coding: utf-8 -*-
"""
MEGAMU DASHBOARD - DESIGN SYSTEM & THEME TOKENS
Bảng màu sắc và kiểu dáng Dark Slate hiện đại, tối giản theo phong cách Linear/Vercel.
"""

# Bảng màu Dark Slate hiện đại
class Colors:
    BG_ROOT = "#090d16"         # Nền gốc cửa sổ
    BG_HEADER = "#0d131f"       # Thanh tiêu đề
    BG_NAV = "#0f172a"          # Thanh điều hướng Tab
    BG_SURFACE = "#111827"      # Khung chứa nội dung
    BG_CARD = "#151d30"         # Thẻ Slot / Hàng tài khoản
    BG_CARD_HOVER = "#1c263e"   # Khi rê chuột vào thẻ
    BG_CARD_ACTIVE = "#1e293b"  # Thẻ khi đang bật Auto Train
    BG_INPUT = "#0b101b"        # Ô nhập liệu / dropdown

    # Viền (Borders - Tối giản 1px concentric)
    BORDER_SUBTLE = "#1e293b"
    BORDER_CARD = "#232f48"
    BORDER_FOCUS = "#38bdf8"
    BORDER_SUCCESS = "#22c55e"
    BORDER_DANGER = "#ef4444"

    # Màu chữ (Typography)
    TEXT_MAIN = "#f8fafc"       # Chữ trắng sáng chính
    TEXT_MUTED = "#94a3b8"      # Chữ phụ màu xám nhạt
    TEXT_DIM = "#64748b"        # Chữ mờ ghi chú
    TEXT_DARK = "#475569"       # Chữ tối / disabled

    # Điểm nhấn chức năng (Accents)
    CYAN = "#38bdf8"            # Thao tác chính, liên kết
    GREEN = "#22c55e"           # Đang chạy, thành công
    GREEN_HOVER = "#16a34a"
    AMBER = "#f59e0b"           # Chờ đợi, cảnh báo
    ROSE = "#ef4444"            # Dừng lại, lỗi, đóng
    ROSE_HOVER = "#dc2626"
    PURPLE = "#c084fc"          # Server / Phân loại
    BLUE = "#60a5fa"

    # Trạng thái Slot
    SLOT_STOPPED_BG = "#131a29"
    SLOT_RUNNING_BG = "#0f2327"
    SLOT_RUNNING_BORDER = "#14b8a6"


class Fonts:
    FAMILY = "Segoe UI"
    HEADER_TITLE = (FAMILY, 15, "bold")
    HEADER_SUB = (FAMILY, 11)
    NAV_TAB = (FAMILY, 12, "bold")
    SLOT_TITLE = (FAMILY, 13, "bold")
    BODY = (FAMILY, 11)
    BODY_BOLD = (FAMILY, 11, "bold")
    CAPTION = (FAMILY, 10)
    BADGE = (FAMILY, 10, "bold")
    MONO = ("Consolas", 10)
    COUNTDOWN = (FAMILY, 20, "bold")
