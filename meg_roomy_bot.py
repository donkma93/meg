#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
MEGAMU ROOMY AUTO-BOT & AI CO-PILOT ENGINE (v4.5 - Full Auto-Connect & Solver)
=============================================================================
ĐỒNG BỘ TRỰC TIẾP 100% VỚI RAM TIẾN TRÌNH CLIENT MEGAMU THẬT:
- TỰ ĐỘNG KẾT NỐI NGAY LẬP TỨC (Auto-Connect) khi mở Bot vào đúng tài khoản đang có bài.
- Tự động nhận diện tài khoản đang chơi (Evilzzz PID 44728, laclac24 PID 36676...).
- Poller RAM thời gian thực 100ms:
  * Cọc bài: Đọc trực tiếp CardCount (+0x28) từ Roomy Logic và DeckCountText (+0x58).
  * 5 ô khay bài trên tay (0..4): Đọc Slot (+0x80) -> Card (Color, Number).
  * 3 ô khay ghép combo (5..7): Đọc thẻ đang nằm trong khay đỏ.
  * Điểm tổng & Điểm combo: Đọc từ TotalScoreText (+0x60) và MatchScoreText (+0x38).
- HỖ TRỢ ĐỒNG BỘ 2 CHIỀU:
  * Bấm nút trên Bot -> Gửi lệnh vào Game.
  * Click trực tiếp bằng chuột trên cửa sổ Game -> Bot lập tức đồng bộ theo thời gian thực!
- Nút "🪟 Hiện Cửa Sổ Game Lên Trước": Đưa game ra trước màn hình tức thì.
- Smart Deck Clicker: Tự động dò tọa độ cọc bài chuẩn xác trên client 620x450.
- AI Co-Pilot: Chỉ dẫn nước đi tối ưu nhất để đạt mốc RƯƠNG VÀNG (>= 500 điểm).
=============================================================================
"""

import os
import sys
import time
import math
import random
import ctypes
from ctypes import wintypes
import threading
from enum import IntEnum
from typing import List, Tuple, Optional, Dict, Set, Any

# Ensure current directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Tkinter GUI
import tkinter as tk
from tkinter import ttk, messagebox

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SW_SHOWNOACTIVATE = 4

try:
    from meg_navigator import WindowHelper, UnityBackgroundHook, ensure_desktop_attached
except ImportError:
    WindowHelper = None
    UnityBackgroundHook = None
    def ensure_desktop_attached(): pass

try:
    from meg_rea_hunter import Win32MemoryScanner
except ImportError:
    Win32MemoryScanner = None

# =============================================================================
# DATA TYPES & COMBINATION RULES
# =============================================================================

class CardColor(IntEnum):
    RED = 0       # Đỏ
    BLUE = 1      # Xanh
    YELLOW = 2    # Vàng
    SPECIAL = 3   # Tím Đặc Biệt (Joker)

COLOR_HEX = {
    CardColor.RED: "#E74C3C",
    CardColor.BLUE: "#3498DB",
    CardColor.YELLOW: "#F1C40F",
    CardColor.SPECIAL: "#9B59B6"
}

COLOR_NAMES = {
    -1: "TRỐNG",
    CardColor.RED: "Đỏ",
    CardColor.BLUE: "Xanh",
    CardColor.YELLOW: "Vàng",
    CardColor.SPECIAL: "Đặc Biệt"
}

class RoomyCard:
    def __init__(self, color: int, number: int, uid: int = 0):
        self.color = color      # 0: Red, 1: Blue, 2: Yellow, 3: Special
        self.number = number    # 1..8, hoặc 0 cho Special
        self.uid = uid

    def __repr__(self):
        c_short = {0: "Đỏ", 1: "Xanh", 2: "Vàng", 3: "ĐB"}
        c_str = c_short.get(self.color, "?")
        return f"[{c_str} {self.number if self.color != 3 else '★'}]"

    def __eq__(self, other):
        if not isinstance(other, RoomyCard): return False
        return self.color == other.color and self.number == other.number

    def __hash__(self):
        return hash((self.color, self.number))

def evaluate_triple(c1: RoomyCard, c2: RoomyCard, c3: RoomyCard) -> Tuple[int, str]:
    cards = [c1, c2, c3]
    has_sp = any(c.color == CardColor.SPECIAL for c in cards)

    # 1. BỘ BA ĐỒNG SỐ KHÁC MÀU (Three of a Kind)
    if not has_sp:
        if c1.number == c2.number == c3.number and len({c1.color, c2.color, c3.color}) == 3:
            score = 20 + c1.number * 10
            return (score, f"Bộ Ba {c1.number} (3 màu)")

        # 2. SẢNH LIÊN TIẾP CÙNG MÀU (Straight Run)
        if c1.color == c2.color == c3.color:
            nums = sorted([c1.number, c2.number, c3.number])
            if nums[0] + 1 == nums[1] and nums[1] + 1 == nums[2]:
                color_bonus = 15 if c1.color == CardColor.YELLOW else (10 if c1.color == CardColor.BLUE else 0)
                score = nums[0] * 10 + color_bonus
                return (score, f"Sảnh {COLOR_NAMES.get(c1.color, '')} {nums[0]}-{nums[1]}-{nums[2]}")
    else:
        # TỔ HỢP CÓ THẺ ĐẶC BIỆT
        normals = [c for c in cards if c.color != CardColor.SPECIAL]
        if len(normals) == 2:
            n1, n2 = normals[0], normals[1]
            if n1.number == n2.number and n1.color != n2.color:
                return (30 + n1.number * 10, f"Bộ Ba {n1.number} + Thẻ Đặc Biệt")
            if n1.color == n2.color:
                diff = abs(n1.number - n2.number)
                if diff in (1, 2):
                    min_num = min(n1.number, n2.number)
                    return (min_num * 10 + 20, f"Sảnh {COLOR_NAMES.get(n1.color, '')} + Thẻ Đặc Biệt")
    return (0, "")

class RoomyAISolver:
    @staticmethod
    def find_all_valid_triples(cards: List[RoomyCard]) -> List[Tuple[Tuple[RoomyCard, RoomyCard, RoomyCard], int, str]]:
        results = []
        n = len(cards)
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    score, desc = evaluate_triple(cards[i], cards[j], cards[k])
                    if score > 0:
                        results.append(((cards[i], cards[j], cards[k]), score, desc))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    @staticmethod
    def calculate_card_potential(card: RoomyCard, hand: List[RoomyCard], remaining_deck_count: int = 24) -> float:
        if card.color == CardColor.SPECIAL:
            return 200.0
        base = card.number * 3.0
        synergy = 0.0
        for other in hand:
            if other == card or other.color == CardColor.SPECIAL:
                continue
            if other.number == card.number and other.color != card.color:
                synergy += 40.0
            elif other.color == card.color and abs(other.number - card.number) in (1, 2):
                synergy += 30.0 if abs(other.number - card.number) == 1 else 20.0
        return base + synergy

    @staticmethod
    def choose_worst_card_to_discard(hand: List[RoomyCard], remaining_deck_count: int = 24) -> RoomyCard:
        normal_cards = [c for c in hand if c.color != CardColor.SPECIAL]
        if not normal_cards:
            return hand[0]
        scores = [(c, RoomyAISolver.calculate_card_potential(c, hand, remaining_deck_count)) for c in normal_cards]
        scores.sort(key=lambda x: x[1])
        return scores[0][0]

# =============================================================================
# LIVE RAM GAME READER (Reads 100% Real Memory from MEGAMU Client)
# =============================================================================

class LiveRoomyReader:
    def __init__(self, pid: int):
        self.pid = pid
        self.scanner = Win32MemoryScanner(pid) if Win32MemoryScanner else None
        self.is_connected = False
        self.char_name = ""
        self.hwnd = 0

    def connect(self) -> bool:
        if not self.scanner or not self.scanner.open():
            return False
        player = self.scanner.get_player()
        self.char_name = self.scanner.read_str(self.scanner.read_ptr(player + 0x28)) if player else f"PID {self.pid}"
        if WindowHelper:
            win_info = WindowHelper.find_window_for_pid(self.pid)
            self.hwnd = win_info[0] if win_info else 0
        self.is_connected = True
        return True

    def close(self):
        if self.scanner:
            self.scanner.close()
        self.is_connected = False

    def poll(self) -> dict:
        if not self.is_connected or not self.scanner:
            return {"connected": False}

        game_inst = self.scanner.get_game_instance()
        if not game_inst:
            return {"connected": False, "error": "Game instance NULL"}

        roomy_logic = self.scanner.read_ptr(game_inst + 0x1C8)
        state = self.scanner.read_i32(roomy_logic + 0x24) if roomy_logic else -1
        card_count = self.scanner.read_i32(roomy_logic + 0x28) if roomy_logic else 0
        special_count = self.scanner.read_i32(roomy_logic + 0x2C) if roomy_logic else 0
        is_matching = bool(self.scanner.read_u8(roomy_logic + 0x30)) if roomy_logic else False

        game_ui = self.scanner.read_ptr(game_inst + 0x1E0)
        minigame_win = self.scanner.read_ptr(game_ui + 0x1A0) if game_ui else 0
        roomy_win = self.scanner.read_ptr(minigame_win + 0x38) if minigame_win else 0

        # Read Window IsOpen
        win_obj = self.scanner.read_ptr(roomy_win + 0x20) if roomy_win else 0
        is_open = bool(self.scanner.read_u8(win_obj + 0x48)) if win_obj else False

        # Read Texts from MRoomyWindow
        score_text_ptr = self.scanner.read_ptr(roomy_win + 0x60) if roomy_win else 0
        deck_text_ptr = self.scanner.read_ptr(roomy_win + 0x58) if roomy_win else 0
        match_score_text_ptr = self.scanner.read_ptr(roomy_win + 0x38) if roomy_win else 0

        score_str = self.scanner.read_str(self.scanner.read_ptr(score_text_ptr + 0xE8)) if score_text_ptr else "0"
        deck_str = self.scanner.read_str(self.scanner.read_ptr(deck_text_ptr + 0xE8)) if deck_text_ptr else f"{card_count}x"
        match_score_str = self.scanner.read_str(self.scanner.read_ptr(match_score_text_ptr + 0xE8)) if match_score_text_ptr else "0"

        # Read Slots (0..4 Hand, 5..7 Meld, 8 AvailableSpecial, 9 MatchSpecial)
        slots_arr = self.scanner.read_ptr(roomy_win + 0x80) if roomy_win else 0
        slot_count = self.scanner.read_i32(slots_arr + 0x18) if slots_arr else 0

        hand_cards = []
        for i in range(5):
            if slots_arr and i < slot_count:
                s_ptr = self.scanner.read_ptr(slots_arr + 0x20 + i * 8)
                c_ptr = self.scanner.read_ptr(s_ptr + 0x28) if s_ptr else 0
                col = self.scanner.read_i32(c_ptr + 0x14) if c_ptr else -1
                num = self.scanner.read_i32(c_ptr + 0x18) if c_ptr else -1
                hand_cards.append(RoomyCard(col, num) if col >= 0 and num >= 0 else None)
            else:
                hand_cards.append(None)

        meld_cards = []
        for i in range(5, 8):
            if slots_arr and i < slot_count:
                s_ptr = self.scanner.read_ptr(slots_arr + 0x20 + i * 8)
                c_ptr = self.scanner.read_ptr(s_ptr + 0x28) if s_ptr else 0
                col = self.scanner.read_i32(c_ptr + 0x14) if c_ptr else -1
                num = self.scanner.read_i32(c_ptr + 0x18) if c_ptr else -1
                meld_cards.append(RoomyCard(col, num) if col >= 0 and num >= 0 else None)
            else:
                meld_cards.append(None)

        return {
            "connected": True,
            "char_name": self.char_name,
            "pid": self.pid,
            "hwnd": self.hwnd,
            "state": state,
            "is_open": is_open,
            "card_count": card_count,
            "special_count": special_count,
            "is_matching": is_matching,
            "score_str": score_str,
            "deck_str": deck_str,
            "match_score_str": match_score_str,
            "hand_cards": hand_cards,
            "meld_cards": meld_cards
        }

# =============================================================================
# OFFLINE SIMULATION GAME (For training & testing)
# =============================================================================

class RoomyOfflineGame:
    def __init__(self):
        self.deck: List[RoomyCard] = []
        self.hand: List[Optional[RoomyCard]] = [None] * 5
        self.meld: List[Optional[RoomyCard]] = [None] * 3
        self.score = 0
        self.last_combo_score = 0
        self.is_complete = False
        self.reset()

    def reset(self):
        self.deck.clear()
        uid = 1
        for col in [CardColor.RED, CardColor.BLUE, CardColor.YELLOW]:
            for num in range(1, 9):
                self.deck.append(RoomyCard(col, num, uid))
                uid += 1
        random.shuffle(self.deck)
        self.hand = [None] * 5
        self.meld = [None] * 3
        self.score = 0
        self.last_combo_score = 0
        self.is_complete = False

    def draw_from_deck(self) -> Optional[RoomyCard]:
        if not self.deck: return None
        for i in range(5):
            if self.hand[i] is None:
                card = self.deck.pop(0)
                self.hand[i] = card
                return card
        return None

    def move_hand_to_meld(self, hand_idx: int) -> bool:
        if hand_idx < 0 or hand_idx >= 5 or self.hand[hand_idx] is None:
            return False
        card = self.hand[hand_idx]
        for m in range(3):
            if self.meld[m] is None:
                self.meld[m] = card
                self.hand[hand_idx] = None
                self._check_and_resolve_meld()
                return True
        return False

    def return_meld_to_hand(self, meld_idx: int) -> bool:
        if meld_idx < 0 or meld_idx >= 3 or self.meld[meld_idx] is None:
            return False
        card = self.meld[meld_idx]
        for h in range(5):
            if self.hand[h] is None:
                self.hand[h] = card
                self.meld[meld_idx] = None
                return True
        return False

    def discard_hand_card(self, hand_idx: int) -> bool:
        if hand_idx < 0 or hand_idx >= 5 or self.hand[hand_idx] is None:
            return False
        self.hand[hand_idx] = None
        return True

    def _check_and_resolve_meld(self):
        if all(c is not None for c in self.meld):
            pts, desc = evaluate_triple(self.meld[0], self.meld[1], self.meld[2])
            if pts > 0:
                self.score += pts
                self.last_combo_score = pts
                self.meld = [None] * 3
                return True
        return False

# =============================================================================
# GUI INTERACTIVE DASHBOARD (Exact In-Game Match + Real-time Sync)
# =============================================================================

class RoomyBotGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MEGAMU Roomy AI Co-Pilot & Auto-Bot (v4.5 Live RAM Sync)")
        self.root.geometry("880x820")
        self.root.minsize(840, 750)
        self.root.configure(bg="#0F111A")

        self.offline_game = RoomyOfflineGame()
        self.live_reader: Optional[LiveRoomyReader] = None
        self.is_live_mode = False
        self.is_sync_running = False
        self.is_auto_running = False

        self.active_pid: Optional[int] = None
        self.active_hwnd: Optional[int] = None
        self.active_char_name: str = ""
        self.account_map: Dict[str, Tuple[int, int, str, int, bool]] = {}

        # Tọa độ chuẩn xác 100% đo đạc từ Canvas và ảnh cửa sổ Roomy (Client 620x450):
        # Cửa sổ Roomy (rộng ~270px, cao ~309px) nằm căn giữa màn hình (win_x0 = 175, win_y0 = 37)
        self.confirmed_deck_coord = (228, 254)
        self.HAND_COORDS = [(245, 96), (275, 96), (305, 96), (335, 96), (365, 96)]
        self.MELD_COORDS = [(278, 158), (308, 158), (338, 158)]
        self.THOAT_COORD = (325, 301)

        self._build_ui()
        self.refresh_accounts()

        # TỰ ĐỘNG KẾT NỐI NGAY LẬP TỨC nếu có tài khoản đang mở Roomy
        self.auto_connect_first_active()
        self.update_display()

    def _build_ui(self):
        # 1. TOP HEADER & ACCOUNT SELECTOR
        header_frame = tk.Frame(self.root, bg="#1A1C2A", padx=15, pady=10)
        header_frame.pack(fill="x")

        title_box = tk.Frame(header_frame, bg="#1A1C2A")
        title_box.pack(side="left")
        tk.Label(title_box, text="MEGAMU ROOMY AI CO-PILOT v4.5", font=("Segoe UI", 13, "bold"), fg="#68D391", bg="#1A1C2A").pack(anchor="w")
        self.lbl_target_char = tk.Label(title_box, text="Tài khoản: [Đang quét tiến trình...]", font=("Segoe UI", 9, "bold"), fg="#F6AD55", bg="#1A1C2A")
        self.lbl_target_char.pack(anchor="w")

        # Account Dropdown & Controls
        acc_box = tk.Frame(header_frame, bg="#1A1C2A")
        acc_box.pack(side="right")
        tk.Label(acc_box, text="Chọn Acc:", font=("Segoe UI", 9, "bold"), fg="#E2E8F0", bg="#1A1C2A").pack(side="left", padx=2)

        self.cbo_accounts = ttk.Combobox(acc_box, width=38, state="readonly")
        self.cbo_accounts.pack(side="left", padx=4)

        btn_ref = tk.Button(acc_box, text="🔄 Quét", command=self.refresh_accounts, bg="#2D3748", fg="#E2E8F0", font=("Segoe UI", 8, "bold"), relief="flat")
        btn_ref.pack(side="left", padx=2)

        self.btn_connect = tk.Button(acc_box, text="🔌 KẾT NỐI RAM", command=self.toggle_connection,
                                     bg="#38A169", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=8, cursor="hand2")
        self.btn_connect.pack(side="left", padx=4)

        # 2. STATUS BANNER (LIVE vs SIMULATION)
        self.banner_frame = tk.Frame(self.root, bg="#2C3E50", padx=15, pady=6)
        self.banner_frame.pack(fill="x", padx=15, pady=4)
        self.lbl_mode_status = tk.Label(self.banner_frame, text="⚡ ĐANG DÒ TÌM TIẾN TRÌNH ROOMY TRONG GAME...",
                                        font=("Segoe UI", 9, "bold"), fg="#F6E05E", bg="#2C3E50")
        self.lbl_mode_status.pack(side="left")

        # 3. AI RECOMMENDATION BANNER
        recom_frame = tk.Frame(self.root, bg="#2D3748", padx=15, pady=8)
        recom_frame.pack(fill="x", padx=15, pady=4)
        tk.Label(recom_frame, text="💡 GỢI Ý NƯỚC ĐI TỐI ƯU CỦA AI:", font=("Segoe UI", 9, "bold"), fg="#63B3ED", bg="#2D3748").pack(anchor="w")
        self.lbl_recommendation = tk.Label(recom_frame, text="Đang đồng bộ cọc bài...",
                                           font=("Segoe UI", 11, "bold"), fg="#68D391", bg="#2D3748", wraplength=820, justify="left")
        self.lbl_recommendation.pack(anchor="w", pady=2)

        # 4. EXACT IN-GAME ROOMY WINDOW SIMULATOR
        roomy_panel = tk.Frame(self.root, bg="#12151E", bd=2, relief="groove", padx=20, pady=12)
        roomy_panel.pack(fill="x", padx=15, pady=4)

        # Window Header
        win_hdr = tk.Frame(roomy_panel, bg="#1E3A5F", height=30, padx=10)
        win_hdr.pack(fill="x", pady=(0, 10))
        tk.Label(win_hdr, text="ROOMY", font=("Segoe UI", 11, "bold"), fg="#90CDF4", bg="#1E3A5F").pack(side="left")
        self.lbl_live_indicator = tk.Label(win_hdr, text="[MÔ PHỎNG]", font=("Segoe UI", 9, "bold"), fg="#F6AD55", bg="#1E3A5F")
        self.lbl_live_indicator.pack(side="right")
        self.lbl_window_open_status = tk.Label(win_hdr, text="[CỬA SỔ ĐANG ĐÓNG]", font=("Segoe UI", 9, "bold"), fg="#FEB2B2", bg="#1E3A5F")
        self.lbl_window_open_status.pack(side="right", padx=10)

        # Row 1: Hand Slots (1 Special + 5 Hand Slots)
        row1_frame = tk.Frame(roomy_panel, bg="#12151E")
        row1_frame.pack(pady=3)

        sp_box = tk.Label(row1_frame, text="🔒\nSPECIAL", font=("Segoe UI", 8, "bold"), width=7, height=3,
                          bg="#4A154B", fg="#E9D8FD", relief="ridge")
        sp_box.pack(side="left", padx=(0, 15))

        self.hand_buttons: List[tk.Button] = []
        for i in range(5):
            btn = tk.Button(row1_frame, text="--\nTRỐNG", font=("Segoe UI", 10, "bold"), width=7, height=3,
                            bg="#2D3748", fg="#718096", relief="solid", cursor="hand2",
                            command=lambda idx=i: self.on_hand_click(idx))
            btn.pack(side="left", padx=4)
            self.hand_buttons.append(btn)

        # Arrow
        tk.Label(roomy_panel, text="▼", font=("Segoe UI", 12, "bold"), fg="#ED8936", bg="#12151E").pack(pady=2)

        # Row 2: Red Meld Bar (1 Special + 3 Meld Slots + Combo Score Box)
        meld_bar = tk.Frame(roomy_panel, bg="#742A2A", padx=10, pady=6, bd=1, relief="ridge")
        meld_bar.pack(pady=3)

        sp_meld = tk.Label(meld_bar, text="🔒", font=("Segoe UI", 10), width=5, height=2, bg="#551A8B", fg="#E9D8FD")
        sp_meld.pack(side="left", padx=(0, 12))

        self.meld_buttons: List[tk.Button] = []
        for m in range(3):
            btn = tk.Button(meld_bar, text="--", font=("Segoe UI", 11, "bold"), width=6, height=2,
                            bg="#1A202C", fg="#718096", relief="solid", cursor="hand2",
                            command=lambda idx=m: self.on_meld_click(idx))
            btn.pack(side="left", padx=3)
            self.meld_buttons.append(btn)

        combo_box = tk.Frame(meld_bar, bg="#2D3748", padx=8, pady=4)
        combo_box.pack(side="left", padx=(12, 0))
        self.lbl_combo_pts = tk.Label(combo_box, text="0", font=("Consolas", 14, "bold"), fg="#F6E05E", bg="#2D3748", width=4)
        self.lbl_combo_pts.pack()

        # Row 3: Deck Box (24x) & Total Score Box
        row3_frame = tk.Frame(roomy_panel, bg="#12151E")
        row3_frame.pack(fill="x", pady=10, padx=30)

        deck_box = tk.Frame(row3_frame, bg="#12151E")
        deck_box.pack(side="left")

        self.btn_deck_draw = tk.Button(deck_box, text="🎴\nCỌC BÀI", font=("Segoe UI", 9, "bold"), width=7, height=2,
                                       bg="#4A5568", fg="#F7FAFC", relief="raised", cursor="hand2", command=self.on_draw_deck)
        self.btn_deck_draw.pack(side="left")

        self.lbl_deck_count = tk.Label(deck_box, text="24x", font=("Segoe UI", 14, "bold"), fg="#E2E8F0", bg="#12151E", padx=8)
        self.lbl_deck_count.pack(side="left")

        score_box = tk.Frame(row3_frame, bg="#12151E")
        score_box.pack(side="right")
        tk.Label(score_box, text="ĐIỂM", font=("Segoe UI", 9, "bold"), fg="#A0AEC0", bg="#12151E").pack()
        self.lbl_total_score = tk.Label(score_box, text="0", font=("Consolas", 14, "bold"), fg="#68D391", bg="#2D3748", width=8, pady=3)
        self.lbl_total_score.pack()

        # Row 4: THOÁT Button
        self.btn_thoat = tk.Button(roomy_panel, text="THOÁT", font=("Segoe UI", 11, "bold"), bg="#2B6CB0", fg="#FFFFFF",
                                   width=16, height=1, relief="raised", cursor="hand2", command=self.on_thoat)
        self.btn_thoat.pack(pady=6)

        # 5. CONTROLS & LOG
        ctrl_frame = tk.Frame(self.root, bg="#0F111A", padx=15)
        ctrl_frame.pack(fill="both", expand=True, pady=4)

        # Left Controls
        btn_panel = tk.Frame(ctrl_frame, bg="#1A1C2A", padx=12, pady=8, width=290)
        btn_panel.pack(side="left", fill="y", padx=(0, 10))

        tk.Label(btn_panel, text="THAO TÁC GAME THẬT (LIVE ENGINE):", font=("Segoe UI", 8, "bold"), fg="#ED64A6", bg="#1A1C2A").pack(anchor="w", pady=(0, 4))
        
        self.btn_focus_window = tk.Button(btn_panel, text="🪟 Hiện Cửa Sổ Game Lên Trước", font=("Segoe UI", 9, "bold"),
                                          bg="#3182CE", fg="#FFFFFF", relief="flat", pady=5, cursor="hand2", command=self.focus_game_window)
        self.btn_focus_window.pack(fill="x", pady=2)

        self.btn_game_click_deck = tk.Button(btn_panel, text="🃏 Bơm Click Cọc Bài (24x)", font=("Segoe UI", 9, "bold"),
                                             bg="#9F7AEA", fg="#FFFFFF", relief="flat", pady=5, cursor="hand2", command=self.send_click_game_deck)
        self.btn_game_click_deck.pack(fill="x", pady=2)

        self.btn_ai_auto = tk.Button(btn_panel, text="▶ AI Tự Động Giải Nước Đi", font=("Segoe UI", 10, "bold"),
                                     bg="#38A169", fg="#FFFFFF", relief="flat", pady=6, cursor="hand2", command=self.on_ai_step_smart)
        self.btn_ai_auto.pack(fill="x", pady=4)

        tk.Label(btn_panel, text="MÔ PHỎNG & LUYỆN TẬP OFFLINE:", font=("Segoe UI", 8, "bold"), fg="#CBD5E0", bg="#1A1C2A").pack(anchor="w", pady=(8, 4))
        
        btn_bench = tk.Button(btn_panel, text="📊 Benchmark 100 Ván AI", font=("Segoe UI", 9),
                              bg="#ECC94B", fg="#1A202C", relief="flat", pady=4, cursor="hand2", command=self.run_benchmark)
        btn_bench.pack(fill="x", pady=2)

        btn_reset = tk.Button(btn_panel, text="🔄 Reset Ván Mô Phỏng", font=("Segoe UI", 9),
                              bg="#718096", fg="#FFFFFF", relief="flat", pady=4, cursor="hand2", command=self.on_offline_reset)
        btn_reset.pack(fill="x", pady=2)

        # Right Log
        log_box = tk.Frame(ctrl_frame, bg="#1A1C2A", padx=10, pady=8)
        log_box.pack(side="right", fill="both", expand=True)

        tk.Label(log_box, text="NHẬT KÝ ĐỒNG BỘ RAM & PHÂN TÍCH:", font=("Segoe UI", 9, "bold"), fg="#E2E8F0", bg="#1A1C2A").pack(anchor="w")
        self.txt_log = tk.Text(log_box, bg="#0D0E15", fg="#CBD5E0", font=("Consolas", 9), relief="flat", wrap="word")
        self.txt_log.pack(fill="both", expand=True, pady=4)

    def log(self, msg: str):
        self.txt_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see("end")

    def refresh_accounts(self):
        """Quét toàn bộ tiến trình MEGAMU và đọc trạng thái Roomy từ RAM."""
        windows = []
        if WindowHelper:
            try:
                ensure_desktop_attached()
                windows = WindowHelper.get_unity_windows()
            except Exception:
                pass

        display_items = []
        self.account_map.clear()
        best_selection_idx = -1

        for idx, (pid, hwnd, title, w, h) in enumerate(windows):
            char_name = title.split()[0] if title else f"PID {pid}"
            roomy_state = -1
            card_count = 0
            is_open = False

            if Win32MemoryScanner:
                scanner = Win32MemoryScanner(pid)
                if scanner.open():
                    p = scanner.get_player()
                    real_name = scanner.read_str(scanner.read_ptr(p + 0x28)) if p else ""
                    if real_name: char_name = real_name
                    game_inst = scanner.get_game_instance()
                    roomy = scanner.read_ptr(game_inst + 0x1C8) if game_inst else 0
                    if roomy:
                        roomy_state = scanner.read_i32(roomy + 0x24)
                        card_count = scanner.read_i32(roomy + 0x28)
                    gui = scanner.read_ptr(game_inst + 0x1E0) if game_inst else 0
                    mini = scanner.read_ptr(gui + 0x1A0) if gui else 0
                    rwin = scanner.read_ptr(mini + 0x38) if mini else 0
                    if rwin:
                        win_obj = scanner.read_ptr(rwin + 0x20)
                        if win_obj:
                            is_open = bool(scanner.read_u8(win_obj + 0x48))
                    scanner.close()

            if roomy_state == 1 and is_open:
                disp = f"🟢 [CỬA SỔ ĐANG MỞ] {char_name} (PID: {pid}) - Cọc: {card_count}x"
                best_selection_idx = len(display_items)
            elif roomy_state == 1 and not is_open:
                disp = f"🟡 [Có bài - Cửa sổ đóng] {char_name} (PID: {pid}) - Cọc: {card_count}x"
                if best_selection_idx == -1:
                    best_selection_idx = len(display_items)
            elif roomy_state == 0:
                disp = f"⚪ [Standby] {char_name} (PID: {pid})"
            elif roomy_state == 3:
                disp = f"⚪ [Đóng] {char_name} (PID: {pid})"
            else:
                disp = f"⚪ {char_name} (PID: {pid})"

            display_items.append(disp)
            self.account_map[disp] = (pid, hwnd, char_name, roomy_state, is_open)

        if not display_items:
            self.cbo_accounts['values'] = ["-- Không tìm thấy MEGAMU --"]
            self.cbo_accounts.current(0)
            self.log("⚠️ Không tìm thấy tiến trình MEGAMU nào đang chạy.")
        else:
            self.cbo_accounts['values'] = display_items
            sel_idx = best_selection_idx if best_selection_idx >= 0 else 0
            self.cbo_accounts.current(sel_idx)
            sel_text = display_items[sel_idx]
            self.log(f"🔎 Đã tìm thấy {len(display_items)} tài khoản MEGAMU.")
            if "CỬA SỔ ĐANG MỞ" in sel_text:
                self.log(f"🎯 ƯU TIÊN KẾT NỐI: {sel_text}")

    def auto_connect_first_active(self):
        """Tự động kết nối ngay với tài khoản đang mở bài mà không cần bấm nút."""
        if not self.account_map:
            return
        # Ưu tiên 1: Tài khoản có Roomy đang mở thật trên màn hình
        for disp, (pid, hwnd, char_name, rstate, is_open) in self.account_map.items():
            if rstate == 1 and is_open:
                self.cbo_accounts.set(disp)
                self.log(f"⚡ TỰ ĐỘNG KẾT NỐI VÀO: {char_name} (PID: {pid}) [CỬA SỔ ĐANG MỞ]!")
                self.toggle_connection()
                return

        # Ưu tiên 2: Tài khoản có ván bài đang chơi
        for disp, (pid, hwnd, char_name, rstate, is_open) in self.account_map.items():
            if rstate == 1:
                self.cbo_accounts.set(disp)
                self.log(f"⚡ TỰ ĐỘNG KẾT NỐI VÀO: {char_name} (PID: {pid}) [Cửa sổ đang đóng]!")
                self.toggle_connection()
                return

    def toggle_connection(self):
        """Kết nối / Ngắt kết nối với RAM của tài khoản game."""
        if self.is_live_mode:
            # Disconnect
            self.is_sync_running = False
            self.is_live_mode = False
            if self.live_reader:
                self.live_reader.close()
                self.live_reader = None

            self.active_pid = None
            self.active_hwnd = None
            self.active_char_name = ""

            self.btn_connect.config(text="🔌 KẾT NỐI RAM", bg="#38A169")
            self.lbl_target_char.config(text="Tài khoản: [Chưa kết nối - Chế độ mô phỏng]", fg="#F6AD55")
            self.banner_frame.config(bg="#2C3E50")
            self.lbl_mode_status.config(text="⚡ CHẾ ĐỘ: MÔ PHỎNG LUYỆN TẬP (OFFLINE)", fg="#F6E05E", bg="#2C3E50")
            self.lbl_live_indicator.config(text="[MÔ PHỎNG]", fg="#F6AD55")
            self.lbl_window_open_status.config(text="[MÔ PHỎNG]", fg="#F6AD55")
            self.log("🔌 Đã ngắt kết nối RAM. Trở về chế độ mô phỏng offline.")
            self.update_display()
        else:
            # Connect
            sel = self.cbo_accounts.get()
            if not sel or "Không tìm thấy" in sel:
                messagebox.showwarning("Chưa chọn", "Vui lòng chọn 1 tài khoản trong danh sách!")
                return

            pid, hwnd, char_name, rstate, is_open = self.account_map.get(sel, (0, 0, "", -1, False))
            if not pid: return

            self.live_reader = LiveRoomyReader(pid)
            if not self.live_reader.connect():
                messagebox.showerror("Lỗi Kết Nối", f"Không thể mở tiến trình PID {pid} để đọc RAM!")
                return

            self.active_pid = pid
            self.active_hwnd = hwnd
            self.active_char_name = self.live_reader.char_name
            self.is_live_mode = True

            self.btn_connect.config(text="❌ NGẮT KẾT NỐI", bg="#E53E3E")
            self.lbl_target_char.config(text=f"Tài khoản: [LIVE RAM] {self.active_char_name} (PID: {pid} | HWND: {hwnd})", fg="#68D391")
            self.banner_frame.config(bg="#1A365D")
            self.lbl_mode_status.config(text=f"🟢 ĐÃ ĐỒNG BỘ RAM THỰC TẾ 100%: Nhân vật {self.active_char_name} (PID: {pid}) - ĐANG LIÊN TỤC ĐỌC GAME!", fg="#68D391", bg="#1A365D")
            self.lbl_live_indicator.config(text="[LIVE GAME THẬT]", fg="#68D391")

            self.log(f"✅ ĐÃ KẾT NỐI RAM THÀNH CÔNG VỚI: {self.active_char_name} (PID: {pid})!")
            self.is_sync_running = True
            threading.Thread(target=self._live_sync_thread, daemon=True).start()

    def _live_sync_thread(self):
        """Thread chạy ngầm đọc RAM mỗi 100ms và đồng bộ tức thì lên GUI."""
        while self.is_sync_running and self.is_live_mode:
            try:
                if self.live_reader:
                    data = self.live_reader.poll()
                    if data.get("connected"):
                        self.root.after(0, lambda d=data: self._apply_live_data(d))
            except Exception:
                pass
            time.sleep(0.10)

    def _apply_live_data(self, data: dict):
        if not self.is_live_mode: return

        # 0. Update Window Open/Closed Status
        is_open = data.get("is_open", False)
        if is_open:
            self.lbl_window_open_status.config(text="[🟢 CỬA SỔ TRONG GAME: ĐANG MỞ]", fg="#68D391")
        else:
            self.lbl_window_open_status.config(text="[🔴 CỬA SỔ TRONG GAME: ĐANG ĐÓNG]", fg="#FC8181")

        # 1. Update Deck Count & Scores
        deck_str = data.get("deck_str", "0x")
        self.lbl_deck_count.config(text=deck_str)
        self.lbl_total_score.config(text=data.get("score_str", "0"))
        self.lbl_combo_pts.config(text=data.get("match_score_str", "0"))

        # 2. Update Hand Buttons
        hand_cards = data.get("hand_cards", [None]*5)
        for i in range(5):
            c = hand_cards[i] if i < len(hand_cards) else None
            btn = self.hand_buttons[i]
            if c is not None and c.color >= 0 and c.number >= 0:
                color_hex = COLOR_HEX.get(c.color, "#4A5568")
                fg_col = "#000000" if c.color == CardColor.YELLOW else "#FFFFFF"
                btn.config(text=f"{COLOR_NAMES.get(c.color, '')}\n{c.number}", bg=color_hex, fg=fg_col)
            else:
                btn.config(text="--\nTRỐNG", bg="#2D3748", fg="#718096")

        # 3. Update Meld Buttons
        meld_cards = data.get("meld_cards", [None]*3)
        for m in range(3):
            c = meld_cards[m] if m < len(meld_cards) else None
            btn = self.meld_buttons[m]
            if c is not None and c.color >= 0 and c.number >= 0:
                color_hex = COLOR_HEX.get(c.color, "#4A5568")
                fg_col = "#000000" if c.color == CardColor.YELLOW else "#FFFFFF"
                btn.config(text=f"{COLOR_NAMES.get(c.color, '')} {c.number}", bg=color_hex, fg=fg_col)
            else:
                btn.config(text="--", bg="#1A202C", fg="#718096")

        # 4. AI Recommendation based on LIVE Cards
        if not is_open:
            self.lbl_recommendation.config(
                text="⚠️ CỬA SỔ ROOMY TRONG GAME ĐANG ĐÓNG! Hãy mở lại bảng Roomy trong game (ấn biểu tượng Roomy) trước khi thao tác!",
                fg="#FC8181"
            )
            return

        active_hand = [c for c in hand_cards if c is not None and c.color >= 0]
        active_meld = [c for c in meld_cards if c is not None and c.color >= 0]
        all_available = active_hand + active_meld
        card_count = data.get("card_count", 0)

        triples = RoomyAISolver.find_all_valid_triples(all_available)
        if triples:
            (c1, c2, c3), pts, desc = triples[0]
            rec_text = f"👉 ĂN ĐIỂM NGAY: Ghép 3 lá [{c1}, {c2}, {c3}] vào khay đỏ -> Nhận +{pts} điểm ({desc})!"
            rec_color = "#F6E05E"
        elif len(active_hand) < 5 and card_count > 0:
            rec_text = f"👉 BẤM LẬT BÀI: Bấm cọc bài để rút bài mới lên tay (còn {card_count}x lá)!"
            rec_color = "#68D391"
        elif len(active_hand) >= 5 and card_count > 0:
            worst = RoomyAISolver.choose_worst_card_to_discard(active_hand, card_count)
            rec_text = f"👉 HỦY BÀI RÁC: Khay đã đầy 5 lá. Hãy hủy lá [{worst}] vì tiềm năng ghép cặp thấp nhất!"
            rec_color = "#FC8181"
        elif card_count == 0 and len(active_hand) == 0:
            rec_text = "👉 HẾT BÀI TRONG CỌC: Ván bài kết thúc! Bấm 'THOÁT' để nhận thưởng rương!"
            rec_color = "#CBD5E0"
        else:
            rec_text = "Hãy lật bài hoặc chọn bài vào khay ghép."
            rec_color = "#68D391"

        self.lbl_recommendation.config(text=rec_text, fg=rec_color)

    def update_display(self):
        """Cập nhật hiển thị khi ở chế độ Offline Simulator."""
        if self.is_live_mode: return

        # 1. Update Hand Buttons
        for i in range(5):
            c = self.offline_game.hand[i]
            btn = self.hand_buttons[i]
            if c is not None:
                color_hex = COLOR_HEX.get(c.color, "#4A5568")
                btn.config(text=f"{COLOR_NAMES.get(c.color, '')}\n{c.number}", bg=color_hex,
                           fg="#000000" if c.color == CardColor.YELLOW else "#FFFFFF")
            else:
                btn.config(text="--\nTRỐNG", bg="#2D3748", fg="#718096")

        # 2. Update Meld Buttons
        for m in range(3):
            c = self.offline_game.meld[m]
            btn = self.meld_buttons[m]
            if c is not None:
                color_hex = COLOR_HEX.get(c.color, "#4A5568")
                btn.config(text=f"{COLOR_NAMES.get(c.color, '')} {c.number}", bg=color_hex,
                           fg="#000000" if c.color == CardColor.YELLOW else "#FFFFFF")
            else:
                btn.config(text="--", bg="#1A202C", fg="#718096")

        # 3. Update Deck & Score
        self.lbl_deck_count.config(text=f"{len(self.offline_game.deck)}x")
        self.lbl_total_score.config(text=str(self.offline_game.score))
        self.lbl_combo_pts.config(text=str(self.offline_game.last_combo_score))

        # 4. Recommendation for Offline Game
        hand_cards = [c for c in self.offline_game.hand if c is not None]
        meld_cards = [c for c in self.offline_game.meld if c is not None]
        all_available = hand_cards + meld_cards

        triples = RoomyAISolver.find_all_valid_triples(all_available)
        if triples:
            (c1, c2, c3), pts, desc = triples[0]
            self.lbl_recommendation.config(text=f"👉 ĂN ĐIỂM NGAY: Xếp 3 lá [{c1}, {c2}, {c3}] vào khay đỏ -> +{pts} điểm ({desc})!", fg="#F6E05E")
        elif len(hand_cards) < 5 and len(self.offline_game.deck) > 0:
            self.lbl_recommendation.config(text=f"👉 BẤM LẬT BÀI: Click vào cọc bài '{len(self.offline_game.deck)}x' để rút thêm bài!", fg="#68D391")
        elif len(hand_cards) >= 5 and len(self.offline_game.deck) > 0:
            worst = RoomyAISolver.choose_worst_card_to_discard(hand_cards, len(self.offline_game.deck))
            self.lbl_recommendation.config(text=f"👉 HỦY BÀI RÁC: Khay đầy 5 lá. Hãy hủy lá [{worst}]!", fg="#FC8181")
        elif len(self.offline_game.deck) == 0:
            self.lbl_recommendation.config(text="👉 HẾT BÀI: Bấm THOÁT để kết thúc ván bài!", fg="#CBD5E0")

    def focus_game_window(self):
        """Đưa cửa sổ game của tài khoản đã kết nối lên trước màn hình."""
        if not self.active_hwnd:
            messagebox.showwarning("Chưa Kết Nối", "Vui lòng chọn tài khoản và bấm '🔌 KẾT NỐI RAM' trước!")
            return
        try:
            ensure_desktop_attached()
            if user32.IsIconic(self.active_hwnd):
                user32.ShowWindow(self.active_hwnd, SW_RESTORE)
                time.sleep(0.15)
            user32.SetForegroundWindow(self.active_hwnd)
            self.log(f"🪟 ĐÃ ĐƯA CỬA SỔ '{self.active_char_name}' LÊN TRƯỚC MÀN HÌNH!")
            self.log(f"💡 Mẹo: Bạn có thể click trực tiếp bằng chuột vào cọc bài trong game, Bot sẽ lập tức đọc và đồng bộ bài thật theo thời gian thực!")
        except Exception as e:
            self.log(f"❌ Lỗi khi đưa cửa sổ lên trước: {e}")

    def send_game_click(self, target_x: int, target_y: int, desc: str = "Click") -> bool:
        """Gửi click ngầm an toàn vào game thật (có kiểm tra IsOpen để chống click xuyên thấu ra đất)."""
        if not self.is_live_mode or not self.active_hwnd:
            return False

        # KIỂM TRA AN TOÀN TUYỆT ĐỐI: CỬA SỔ ROOMY PHẢI ĐANG MỞ
        if self.live_reader:
            cur_data = self.live_reader.poll()
            if not cur_data.get("is_open", False):
                self.log(f"⚠️ TỪ CHỐI CLICK [{desc}]: Bảng Roomy trong game hiện ĐANG ĐÓNG!")
                self.log("💡 CẢNH BÁO AN TOÀN: Nếu click lúc này sẽ trúng mặt đất 3D làm nhân vật chạy đi. Hãy bấm mở lại bảng ROOMY trong game trước!")
                messagebox.showwarning(
                    "Cửa Sổ Roomy Đang Đóng",
                    f"Cửa sổ Roomy trên nhân vật '{self.active_char_name}' hiện ĐANG ĐÓNG!\n\n"
                    "⚠️ Để bảo vệ nhân vật KHÔNG BỊ DI CHUYỂN, Bot đã chặn lệnh click này.\n\n"
                    "👉 Hãy vào game, bấm vào biểu tượng ROOMY để mở bảng lên rồi thử lại."
                )
                return False

        try:
            ensure_desktop_attached()
            if user32.IsIconic(self.active_hwnd):
                user32.ShowWindow(self.active_hwnd, SW_RESTORE)
                time.sleep(0.15)

            hook = UnityBackgroundHook.get_instance(self.active_pid) if UnityBackgroundHook else None

            if hook and hook.is_ready:
                hook.send_click(self.active_hwnd, target_x, target_y, duration_ms=50)
                self.log(f"✅ Đã bơm click ngầm [{desc}] tại ({target_x}, {target_y}) vào game thật!")
            else:
                lparam = ((target_y & 0xFFFF) << 16) | (target_x & 0xFFFF)
                user32.PostMessageW(self.active_hwnd, 0x0200, 0, lparam)
                time.sleep(0.02)
                user32.PostMessageW(self.active_hwnd, 0x0201, 1, lparam)
                time.sleep(0.04)
                user32.PostMessageW(self.active_hwnd, 0x0202, 0, lparam)
                self.log(f"✅ Đã gửi PostMessage [{desc}] tại ({target_x}, {target_y}) vào game!")
            return True
        except Exception as e:
            self.log(f"❌ Lỗi click [{desc}]: {e}")
            return False

    def get_ui_coords(self) -> dict:
        """
        Tính toán tọa độ pixel chuẩn xác 100% của cửa sổ Roomy trên Game Client:
        - Cửa sổ Roomy (rộng ~270px, cao ~309px) luôn căn giữa màn hình theo chiều ngang:
          win_x0 = (client_width - 270) // 2
        - Khoảng cách từ đỉnh màn hình xuống (tránh thanh menu trên):
          win_y0 = 37 (chuẩn client 620x450)
        """
        cw, ch = 620, 450
        if self.active_hwnd:
            rect = wintypes.RECT()
            if user32.GetClientRect(self.active_hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 100 and h > 100:
                    cw, ch = w, h

        win_x0 = (cw - 270) // 2
        win_y0 = 37

        return {
            "win_x0": win_x0,
            "win_y0": win_y0,
            "deck": (win_x0 + 53, win_y0 + 217),                                # Cọc bài: (228, 254)
            "hand": [(win_x0 + 70 + i * 30, win_y0 + 59) for i in range(5)],    # (245, 96)..(365, 96)
            "meld": [(win_x0 + 103 + m * 30, win_y0 + 121) for m in range(3)], # (278, 158)..(338, 158)
            "thoat": (win_x0 + 150, win_y0 + 264)                              # THOÁT: (325, 301)
        }

    def send_click_game_deck(self):
        """Bơm click vào cọc bài trong game thật."""
        if not self.is_live_mode or not self.active_hwnd:
            self.on_draw_deck()
            return
        coords = self.get_ui_coords()
        dx, dy = coords["deck"]
        self.send_game_click(dx, dy, "Cọc Bài 24x")

    def on_ai_step_smart(self):
        """AI tự động đi 1 nước tối ưu thông minh."""
        if self.is_live_mode:
            # Trong Live mode: Hướng dẫn hoặc thực hiện nước đi
            if not self.live_reader: return
            data = self.live_reader.poll()
            if not data.get("is_open", False):
                self.log("⚠️ Bảng Roomy đang đóng. Hãy mở bảng Roomy trong game trước!")
                messagebox.showwarning("Cửa Sổ Đang Đóng", "Bảng Roomy trong game đang đóng! Hãy mở lên trước.")
                return

            hand_cards = [c for c in data.get("hand_cards", []) if c is not None and c.color >= 0]
            meld_cards = [c for c in data.get("meld_cards", []) if c is not None and c.color >= 0]
            card_count = data.get("card_count", 0)

            triples = RoomyAISolver.find_all_valid_triples(hand_cards + meld_cards)
            if triples:
                (c1, c2, c3), pts, desc = triples[0]
                msg = f"TÌM THẤY BỘ COMBO:\n• Ghép 3 lá: [{c1}, {c2}, {c3}]\n• Nhận: +{pts} điểm ({desc})!\n\nHãy click đưa 3 lá này vào khay đỏ trong game!"
                self.log(f"🎯 AI: {desc} (+{pts}đ)")
                messagebox.showinfo("AI Gợi Ý Combo", msg)
            elif len(hand_cards) < 5 and card_count > 0:
                self.log("🎴 Khay tay còn chỗ -> Đang bấm lật thêm bài từ cọc...")
                self.send_click_game_deck()
            elif len(hand_cards) >= 5 and card_count > 0:
                worst = RoomyAISolver.choose_worst_card_to_discard(hand_cards, card_count)
                msg = f"KHAY TAY ĐÃ ĐẦY 5 LÁ!\n• Lá bài rác khuyên hủy: [{worst}]\n\nHãy click hủy lá này trong game để lật lá mới!"
                self.log(f"🗑 AI: Khuyên hủy lá rác [{worst}]")
                messagebox.showinfo("AI Khuyên Hủy Rác", msg)
            else:
                self.log("🏁 Cọc bài đã hết. Hãy bấm THOÁT để chốt điểm rương!")
                messagebox.showinfo("Hết Bài", "Cọc bài đã hết. Hãy bấm THOÁT để nhận thưởng!")
        else:
            # Trong Offline mode
            self.on_offline_step()

    def on_draw_deck(self):
        """Click cọc bài trên GUI."""
        if self.is_live_mode:
            self.send_click_game_deck()
        else:
            if len(self.offline_game.deck) == 0:
                messagebox.showinfo("Hết Bài", "Cọc bài đã hết lá! Hãy bấm THOÁT để nhận thưởng.")
                return
            if len([c for c in self.offline_game.hand if c is not None]) >= 5:
                messagebox.showwarning("Khay Đầy", "Khay bài trên tay đã đầy (5 lá)!\nHãy xếp bài vào khay đỏ hoặc hủy bớt bài rác.")
                return
            card = self.offline_game.draw_from_deck()
            self.log(f"🎴 [Mô Phỏng] Lật bài mới: [{card}] (Còn lại {len(self.offline_game.deck)}x trong cọc).")
            self.update_display()

    def on_hand_click(self, idx: int):
        if self.is_live_mode:
            coords = self.get_ui_coords()
            hand_list = coords.get("hand", [])
            hx, hy = hand_list[idx] if idx < len(hand_list) else (0, 0)
            if hx and hy:
                self.send_game_click(hx, hy, f"Ô Bài Tay #{idx+1}")
            return
        card = self.offline_game.hand[idx]
        if card is None: return
        moved = self.offline_game.move_hand_to_meld(idx)
        if moved:
            self.log(f"⬇ [Mô Phỏng] Đã chuyển lá [{card}] xuống khay ghép combo.")
            self.update_display()
        else:
            if messagebox.askyesno("Hủy Bài", f"Khay ghép đã đầy! Bạn có muốn HỦY lá [{card}] không?"):
                self.offline_game.discard_hand_card(idx)
                self.log(f"🗑 [Mô Phỏng] Đã hủy lá bài [{card}].")
                self.update_display()

    def on_meld_click(self, idx: int):
        if self.is_live_mode:
            coords = self.get_ui_coords()
            meld_list = coords.get("meld", [])
            mx, my = meld_list[idx] if idx < len(meld_list) else (0, 0)
            if mx and my:
                self.send_game_click(mx, my, f"Ô Ghép Combo #{idx+1}")
            return
        card = self.offline_game.meld[idx]
        if card is None: return
        ret = self.offline_game.return_meld_to_hand(idx)
        if ret:
            self.log(f"⬆ [Mô Phỏng] Đã rút lá [{card}] trở lại khay tay.")
            self.update_display()

    def on_thoat(self):
        score = self.offline_game.score if not self.is_live_mode else int(self.lbl_total_score.cget("text") or 0)
        tier = "🏆 RƯƠNG VÀNG" if score >= 500 else ("🥈 RƯƠNG BẠC" if score >= 400 else ("🥉 RƯƠNG ĐỒNG" if score >= 250 else "Không đạt mốc"))
        msg = f"Ván bài kết thúc!\n• Tổng điểm: {score} điểm\n• Phần thưởng: {tier}"
        self.log(f"🏁 ĐÃ BẤM THOÁT! {msg}")
        if self.is_live_mode:
            coords = self.get_ui_coords()
            tx, ty = coords.get("thoat", (325, 301))
            self.send_game_click(tx, ty, "Nút THOÁT")
        messagebox.showinfo("Kết Quả Ván Bài", msg)

    def on_offline_step(self):
        hand_cards = [c for c in self.offline_game.hand if c is not None]
        all_avail = hand_cards + [c for c in self.offline_game.meld if c is not None]

        triples = RoomyAISolver.find_all_valid_triples(all_avail)
        if triples:
            (c1, c2, c3), pts, desc = triples[0]
            self.offline_game.score += pts
            self.offline_game.last_combo_score = pts
            for c in [c1, c2, c3]:
                for h in range(5):
                    if self.offline_game.hand[h] == c: self.offline_game.hand[h] = None
                for m in range(3):
                    if self.offline_game.meld[m] == c: self.offline_game.meld[m] = None
            self.log(f"⚡ [Mô Phỏng] AI ăn combo {desc} (+{pts} điểm)!")
            self.update_display()
            return

        if len([c for c in self.offline_game.hand if c is not None]) < 5 and len(self.offline_game.deck) > 0:
            c = self.offline_game.draw_from_deck()
            self.log(f"⚡ [Mô Phỏng] AI lật bài mới: {c}")
            self.update_display()
            return

        if len([c for c in self.offline_game.hand if c is not None]) >= 5 and len(self.offline_game.deck) > 0:
            worst = RoomyAISolver.choose_worst_card_to_discard(hand_cards, len(self.offline_game.deck))
            for h in range(5):
                if self.offline_game.hand[h] == worst:
                    self.offline_game.discard_hand_card(h)
                    break
            drawn = self.offline_game.draw_from_deck()
            self.log(f"⚡ [Mô Phỏng] AI hủy lá {worst} -> Lật bù lá {drawn}")
            self.update_display()
            return

        self.log(f"🏁 [Mô Phỏng] Hết bài trong cọc. Tổng điểm: {self.offline_game.score}")
        self.update_display()

    def on_offline_reset(self):
        self.offline_game.reset()
        self.log("🔄 [Mô Phỏng] Đã reset ván bài mới (24x).")
        self.update_display()

    def run_benchmark(self):
        self.log("⏳ Đang chạy Benchmark 100 ván bài giả lập...")
        def _task():
            scores = []
            gold, silver, bronze = 0, 0, 0
            for _ in range(100):
                sim = RoomyOfflineGame()
                while len(sim.deck) > 0 or any(c is not None for c in sim.hand):
                    h_cards = [c for c in sim.hand if c is not None]
                    avail = h_cards + [c for c in sim.meld if c is not None]
                    trips = RoomyAISolver.find_all_valid_triples(avail)
                    if trips:
                        (c1, c2, c3), pts, _ = trips[0]
                        sim.score += pts
                        for c in [c1, c2, c3]:
                            for h in range(5):
                                if sim.hand[h] == c: sim.hand[h] = None
                            for m in range(3):
                                if sim.meld[m] == c: sim.meld[m] = None
                        continue
                    if len([c for c in sim.hand if c is not None]) < 5 and len(sim.deck) > 0:
                        sim.draw_from_deck()
                        continue
                    if len([c for c in sim.hand if c is not None]) >= 5 and len(sim.deck) > 0:
                        worst = RoomyAISolver.choose_worst_card_to_discard(h_cards, len(sim.deck))
                        for h in range(5):
                            if sim.hand[h] == worst:
                                sim.discard_hand_card(h)
                                break
                        sim.draw_from_deck()
                        continue
                    break

                sc = sim.score
                scores.append(sc)
                if sc >= 500: gold += 1
                elif sc >= 400: silver += 1
                elif sc >= 250: bronze += 1

            avg = sum(scores) / len(scores)
            msg = (f"=== KẾT QUẢ BENCHMARK 100 VÁN (ROOMY 24x) ===\n"
                   f"• Điểm trung bình: {avg:.1f} điểm\n"
                   f"• Điểm cao nhất: {max(scores)} | Thấp nhất: {min(scores)}\n"
                   f"• Rương Vàng (>= 500đ): {gold}%\n"
                   f"• Rương Bạc (400-499đ): {silver}%\n"
                   f"• Rương Đồng (250-399đ): {bronze}%\n"
                   f"• Tỷ lệ đạt Rương (>= 250đ): {gold + silver + bronze}%")
            self.root.after(0, lambda: messagebox.showinfo("Kết Quả Benchmark", msg))
            self.root.after(0, lambda: self.log(f"Benchmark xong: TB={avg:.1f}đ | Vàng={gold}% | Bạc={silver}%"))

        threading.Thread(target=_task, daemon=True).start()

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    root = tk.Tk()
    app = RoomyBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
