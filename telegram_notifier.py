# -*- coding: utf-8 -*-
"""
telegram_notifier.py
Module quản lý gửi thông báo Telegram cho hệ thống MEGAMU, đặc biệt là sự kiện Double Goer (Mirror).
Hỗ trợ:
- Cấu hình chỉ cần duy nhất Bot Token (Hệ thống tự động nhận diện Chat ID qua Telegram Bot API getUpdates)
- Gửi tin nhắn qua Telegram Bot API (urllib chuẩn, không phụ thuộc thư viện ngoài)
- Kiểm tra kết nối (Test connection) và tự động nhận diện người nhận
- Gom nhóm thông báo (Debounce batching) cho nhiều tài khoản vào/ra cổng Mirror cùng lúc
- Gửi bất đồng bộ (non-blocking) qua daemon thread
"""

from __future__ import annotations
import os
import json
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Callable, Any

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
TELEGRAM_CONFIG_FILE = CONFIG_DIR / "telegram_config.json"
MIRROR_CONFIG_FILE = CONFIG_DIR / "mirror_schedule_config.json"


def http_request_with_retry(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
    max_retries: int = 3
) -> Tuple[bool, Any, str]:
    """
    Thực hiện HTTP request tới Telegram API với cơ chế tự động thử lại (Auto-retry).
    Khắc phục triệt để lỗi timeout bắt tay SSL (_ssl.c: The handshake operation timed out)
    do mạng quốc tế chập chờn hoặc độ trễ cao.
    """
    headers = headers or {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "MEGAMU-Bot-Notifier/1.0"
    if data and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    ctx = ssl.create_default_context()
    last_err = ""

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                if res_body.get("ok"):
                    return True, res_body.get("result"), "Thành công."
                return False, None, res_body.get("description", "Lỗi không xác định từ Telegram.")

        except urllib.error.HTTPError as e:
            try:
                err_json = json.loads(e.read().decode("utf-8"))
                desc = err_json.get("description", str(e))
            except Exception:
                desc = str(e)
            if e.code == 401:
                return False, None, f"Bot Token không hợp lệ ({desc})."
            elif e.code == 400:
                return False, None, f"Chưa thể gửi tin: {desc}"
            last_err = f"HTTP {e.code}: {desc}"
            if e.code in (400, 401, 403, 404):
                return False, None, last_err

        except urllib.error.URLError as e:
            reason_str = str(e.reason)
            if "handshake operation timed out" in reason_str:
                last_err = "Độ trễ mạng quốc tế cao: Bắt tay bảo mật SSL quá thời gian chờ (Handshake timed out)."
            else:
                last_err = f"Lỗi kết nối mạng: {reason_str}"

        except Exception as e:
            last_err = f"Lỗi: {e}"

        # Chờ một nhịp ngắn trước khi thử lại
        if attempt < max_retries:
            time.sleep(0.6 * attempt)

    return False, None, last_err


def get_bot_info(token: str, timeout: float = 15.0) -> Tuple[bool, Dict[str, Any], str]:
    """
    Gọi getMe để kiểm tra tính hợp lệ của Bot Token và lấy thông tin bot.
    """
    token = token.strip()
    if not token:
        return False, {}, "Chưa nhập Bot Token Telegram."

    url = f"https://api.telegram.org/bot{token}/getMe"
    ok, res, err = http_request_with_retry(url, timeout=timeout, max_retries=3)
    return ok, (res if isinstance(res, dict) else {}), err


def extract_chat_from_update(up: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Trích xuất thông tin chat từ một update bất kỳ của Telegram Bot API."""
    for key in ("message", "edited_message", "channel_post", "edited_channel_post", "my_chat_member", "callback_query"):
        obj = up.get(key)
        if isinstance(obj, dict):
            if "chat" in obj and isinstance(obj["chat"], dict):
                return obj["chat"]
            if "message" in obj and isinstance(obj["message"], dict) and "chat" in obj["message"]:
                return obj["message"]["chat"]
    return None


def get_bot_updates(token: str, timeout: float = 15.0) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Gọi getUpdates để lấy danh sách tin nhắn mới nhất gửi tới Bot.
    """
    token = token.strip()
    if not token:
        return False, [], "Chưa nhập Bot Token Telegram."

    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=50"
    ok, res, err = http_request_with_retry(url, timeout=timeout, max_retries=3)
    return ok, (res if isinstance(res, list) else []), err


def auto_detect_chat(token: str, timeout: float = 15.0) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Tự động nhận diện Chat ID mới nhất từ Bot Token:
    1. Kiểm tra Token qua getMe
    2. Gọi getUpdates để tìm người/nhóm vừa nhắn tin cho bot
    Trả về: (ok, chat_dict, message/guide)
    """
    token = token.strip()
    if not token:
        return False, None, "Vui lòng nhập Bot Token."

    ok_me, bot_data, err_me = get_bot_info(token, timeout=timeout)
    if not ok_me:
        return False, None, err_me

    bot_user = bot_data.get("username", "bot")
    bot_name = bot_data.get("first_name", "Bot")

    ok_up, updates, err_up = get_bot_updates(token, timeout=timeout)
    if not ok_up:
        return False, {"bot_username": bot_user, "bot_name": bot_name}, f"Lỗi đọc tin nhắn: {err_up}"

    # Tìm các chat trong updates, ưu tiên tin nhắn mới nhất
    found_chats: Dict[str, Dict[str, Any]] = {}
    for up in updates:
        chat = extract_chat_from_update(up)
        if chat and "id" in chat:
            cid = str(chat["id"])
            c_type = chat.get("type", "private")
            c_title = chat.get("title") or chat.get("first_name") or chat.get("username") or cid
            c_user = chat.get("username", "")
            found_chats[cid] = {
                "chat_id": cid,
                "title": c_title,
                "username": c_user,
                "type": c_type,
                "bot_username": bot_user,
                "bot_name": bot_name
            }

    if found_chats:
        # Lấy chat gần nhất (phần tử cuối cùng)
        latest_chat = list(found_chats.values())[-1]
        return True, latest_chat, f"Đã tự động nhận diện chat: {latest_chat['title']} (ID: {latest_chat['chat_id']})"

    guide = (
        f"🤖 Bot '@{bot_user}' ({bot_name}) hợp lệ!\n"
        f"⚠️ Chưa có tin nhắn nào gửi tới bot.\n"
        f"👉 Hãy mở ứng dụng Telegram, tìm kiếm @{bot_user} và bấm 'START' (hoặc gửi 1 tin nhắn bất kỳ), "
        f"sau đó bấm lại nút 'Kiểm tra kết nối'."
    )
    return False, {"bot_username": bot_user, "bot_name": bot_name}, guide


def send_telegram_raw(token: str, chat_id: str, text: str,
                      parse_mode: str = "HTML", timeout: float = 15.0) -> Tuple[bool, str]:
    """
    Gửi tin nhắn trực tiếp qua HTTP REST tới Telegram Bot API với cơ chế tự động thử lại (Retry).
    """
    token = token.strip()
    chat_id = chat_id.strip()

    if not token:
        return False, "Chưa nhập Bot Token Telegram."
    if not chat_id:
        return False, "Chưa xác định được Chat ID để gửi."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        ok, _, err = http_request_with_retry(url, data=data, timeout=timeout, max_retries=3)
        return ok, ("Gửi tin nhắn thành công." if ok else err)
    except Exception as e:
        return False, f"Lỗi không xác định: {e}"


def test_telegram_connection(token: str, chat_id: Optional[str] = None, force_detect: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Kiểm tra kết nối và gửi tin nhắn test:
    - Nếu force_detect=True hoặc chưa có chat_id: Luôn tự động dò tìm chat_id mới nhất từ bot token!
    - Nếu gửi tới chat_id cũ bị lỗi (chat not found), tự động fallback nhận diện lại chat_id từ getUpdates.
    """
    token = token.strip()
    if not token:
        return False, "Vui lòng nhập Bot Token.", None

    chat_data = None
    target_chat_id = (chat_id or "").strip()

    # Luôn tự động nhận diện nếu force_detect hoặc chưa có chat_id
    if force_detect or not target_chat_id:
        ok_det, c_info, msg_det = auto_detect_chat(token)
        if ok_det and c_info and c_info.get("chat_id"):
            chat_data = c_info
            target_chat_id = c_info["chat_id"]
        elif not target_chat_id:
            return False, msg_det, c_info

    now_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    msg = (
        "🤖 <b>[MEGAMU BOT TEST]</b>\n"
        "✅ <b>Kết nối Telegram Bot thành công!</b>\n"
        f"⏰ Thời gian: <code>{now_str}</code>\n"
        "🪞 Hệ thống sẵn sàng tự động báo cáo khi nhân vật vào qua cổng và thoát ra khỏi Mirror."
    )
    ok_send, send_msg = send_telegram_raw(token, target_chat_id, msg)
    if ok_send:
        if not chat_data:
            _, chat_data, _ = auto_detect_chat(token)
        target_name = (chat_data.get("title") if chat_data else "") or target_chat_id
        return True, f"✅ Kết nối thành công! Đã gửi tin nhắn tới: {target_name}.", chat_data

    # TỰ ĐỘNG PHỤC HỒI: Nếu gửi tới target_chat_id bị lỗi (chat not found / unauthorized chat),
    # tự động chạy auto_detect_chat để lấy Chat ID thật từ tin nhắn mới nhất
    if "chat not found" in send_msg.lower() or "bad request" in send_msg.lower():
        ok_det, c_info, msg_det = auto_detect_chat(token)
        if ok_det and c_info and c_info.get("chat_id") and c_info["chat_id"] != target_chat_id:
            chat_data = c_info
            new_cid = c_info["chat_id"]
            ok_send2, send_msg2 = send_telegram_raw(token, new_cid, msg)
            if ok_send2:
                target_name = c_info.get("title") or new_cid
                return True, f"✅ Đã tự động kết nối và gửi tin nhắn tới: {target_name} (ID: {new_cid}).", chat_data
        return False, msg_det, c_info

    return False, f"Lỗi gửi tin: {send_msg}", chat_data


class TelegramConfig:
    """Quản lý nạp / lưu cấu hình Telegram Bot."""

    def __init__(self):
        self._lock = threading.Lock()
        self.bot_token: str = ""
        self.chat_id: str = ""
        self.chat_title: str = ""
        self.bot_username: str = ""
        self.enabled: bool = False
        self.notify_enter: bool = True
        self.notify_exit: bool = True
        self.load()

    def load(self) -> None:
        with self._lock:
            # 1. Thử nạp từ telegram_config.json
            if TELEGRAM_CONFIG_FILE.exists():
                try:
                    data = json.loads(TELEGRAM_CONFIG_FILE.read_text(encoding="utf-8"))
                    self.bot_token = str(data.get("bot_token", "")).strip()
                    self.chat_id = str(data.get("chat_id", "")).strip()
                    self.chat_title = str(data.get("chat_title", "")).strip()
                    self.bot_username = str(data.get("bot_username", "")).strip()
                    self.enabled = bool(data.get("enabled", False))
                    self.notify_enter = bool(data.get("notify_enter", True))
                    self.notify_exit = bool(data.get("notify_exit", True))
                    return
                except Exception:
                    pass

            # 2. Fallback kiểm tra trong mirror_schedule_config.json
            if MIRROR_CONFIG_FILE.exists():
                try:
                    data = json.loads(MIRROR_CONFIG_FILE.read_text(encoding="utf-8"))
                    tg = data.get("telegram", {})
                    if tg:
                        self.bot_token = str(tg.get("bot_token", "")).strip()
                        self.chat_id = str(tg.get("chat_id", "")).strip()
                        self.chat_title = str(tg.get("chat_title", "")).strip()
                        self.bot_username = str(tg.get("bot_username", "")).strip()
                        self.enabled = bool(tg.get("enabled", False))
                        self.notify_enter = bool(tg.get("notify_enter", True))
                        self.notify_exit = bool(tg.get("notify_exit", True))
                except Exception:
                    pass

    def save(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None,
             enabled: Optional[bool] = None, notify_enter: Optional[bool] = None,
             notify_exit: Optional[bool] = None, chat_title: Optional[str] = None,
             bot_username: Optional[str] = None) -> None:
        with self._lock:
            if bot_token is not None:
                self.bot_token = str(bot_token).strip()
            if chat_id is not None:
                self.chat_id = str(chat_id).strip()
            if chat_title is not None:
                self.chat_title = str(chat_title).strip()
            if bot_username is not None:
                self.bot_username = str(bot_username).strip()
            if enabled is not None:
                self.enabled = bool(enabled)
            if notify_enter is not None:
                self.notify_enter = bool(notify_enter)
            if notify_exit is not None:
                self.notify_exit = bool(notify_exit)

            data = {
                "bot_token": self.bot_token,
                "chat_id": self.chat_id,
                "chat_title": self.chat_title,
                "bot_username": self.bot_username,
                "enabled": self.enabled,
                "notify_enter": self.notify_enter,
                "notify_exit": self.notify_exit,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            try:
                tmp = TELEGRAM_CONFIG_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp.replace(TELEGRAM_CONFIG_FILE)
            except Exception as e:
                print(f"[TelegramConfig] Lỗi lưu {TELEGRAM_CONFIG_FILE}: {e}")

            # Đồng bộ sang mirror_schedule_config.json
            try:
                if MIRROR_CONFIG_FILE.exists():
                    m_data = json.loads(MIRROR_CONFIG_FILE.read_text(encoding="utf-8"))
                else:
                    m_data = {}
                m_data["telegram"] = data
                m_tmp = MIRROR_CONFIG_FILE.with_suffix(".tmp")
                m_tmp.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
                m_tmp.replace(MIRROR_CONFIG_FILE)
            except Exception:
                pass

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "bot_token": self.bot_token,
                "chat_id": self.chat_id,
                "chat_title": self.chat_title,
                "bot_username": self.bot_username,
                "enabled": self.enabled,
                "notify_enter": self.notify_enter,
                "notify_exit": self.notify_exit
            }


class _SlotState:
    """Theo dõi trạng thái của 1 slot tham gia Mirror."""
    def __init__(self, slot_idx: int):
        self.slot_idx = slot_idx
        self.confirmed_in_mirror: Optional[bool] = None  # None: chưa xác định (initial)
        self.consecutive_ins = 0
        self.consecutive_outs = 0


class MirrorTelegramNotifier:
    """
    Quản lý theo dõi trạng thái nhân vật và gom nhóm thông báo vào/ra Mirror.
    Debounce 2.0 giây: Nếu nhiều nhân vật vào hoặc ra cùng lúc,
    hệ thống sẽ gom lại thông báo 1 tin duy nhất:
    "Nhân vật A, B, C đã vào qua cổng" hoặc "Nhân vật A, B đã thoát ra".
    Tự động tìm kiếm Chat ID từ Bot Token nếu chưa có Chat ID.
    """

    def __init__(self, config: Optional[TelegramConfig] = None):
        self.config = config or TelegramConfig()
        self._lock = threading.Lock()
        self._slot_states: Dict[int, _SlotState] = {}

        self._pending_enters: List[str] = []
        self._enter_timer: Optional[float] = None

        self._pending_exits: List[str] = []
        self._exit_timer: Optional[float] = None

    def is_enabled(self) -> bool:
        # Chỉ cần người dùng bật và đã nhập Bot Token!
        return bool(self.config.enabled and self.config.bot_token)

    def record_character_state(self, char_name: str, slot_idx: int,
                               is_connected: bool, is_in_mirror: bool) -> None:
        """
        Cập nhật trạng thái của nhân vật ở slot_idx trong mỗi nhịp quét.
        Dùng bộ lọc trễ (hysteresis): 1 nhịp để nhận diện Vào Cổng,
        2 nhịp False liên tiếp để xác nhận Thoát Ra (tránh lỗi nhấp nháy khi chuyển map).
        """
        char_name = str(char_name).strip() if char_name else f"Slot {slot_idx:02d}"
        if char_name in ("", "---", "None"):
            char_name = f"Slot {slot_idx:02d}"

        with self._lock:
            if slot_idx not in self._slot_states:
                self._slot_states[slot_idx] = _SlotState(slot_idx)
            st = self._slot_states[slot_idx]

            # Nếu game ngắt kết nối hoặc tiến trình đóng
            if not is_connected:
                if st.confirmed_in_mirror is True:
                    st.confirmed_in_mirror = False
                    st.consecutive_ins = 0
                    st.consecutive_outs = 0
                    self._enqueue_exit_locked(char_name)
                return

            # Nhịp quan sát đầu tiên
            if st.confirmed_in_mirror is None:
                st.confirmed_in_mirror = is_in_mirror
                st.consecutive_ins = 1 if is_in_mirror else 0
                st.consecutive_outs = 0 if is_in_mirror else 1
                return

            if is_in_mirror:
                st.consecutive_outs = 0
                st.consecutive_ins += 1
                # Chuyển trạng thái: Chưa vào -> ĐÃ VÀO
                if not st.confirmed_in_mirror and st.consecutive_ins >= 1:
                    st.confirmed_in_mirror = True
                    self._enqueue_enter_locked(char_name)
            else:
                st.consecutive_ins = 0
                st.consecutive_outs += 1
                # Chuyển trạng thái: Đang trong -> ĐÃ THOÁT RA (Cần ít nhất 2 nhịp xác nhận)
                if st.confirmed_in_mirror and st.consecutive_outs >= 2:
                    st.confirmed_in_mirror = False
                    self._enqueue_exit_locked(char_name)

    def _enqueue_enter_locked(self, char_name: str) -> None:
        if char_name not in self._pending_enters:
            self._pending_enters.append(char_name)
        if self._enter_timer is None:
            self._enter_timer = time.time()

    def _enqueue_exit_locked(self, char_name: str) -> None:
        if char_name not in self._pending_exits:
            self._pending_exits.append(char_name)
        if self._exit_timer is None:
            self._exit_timer = time.time()

    def check_and_flush(self, log_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Kiểm tra thời gian debounce (2.0s). Nếu đã đến hạn thì gom danh sách và gửi.
        """
        now = time.time()
        enters_to_send: List[str] = []
        exits_to_send: List[str] = []

        with self._lock:
            if self._pending_enters and self._enter_timer and (now - self._enter_timer >= 2.0):
                enters_to_send = list(self._pending_enters)
                self._pending_enters.clear()
                self._enter_timer = None

            if self._pending_exits and self._exit_timer and (now - self._exit_timer >= 2.0):
                exits_to_send = list(self._pending_exits)
                self._pending_exits.clear()
                self._exit_timer = None

        if enters_to_send:
            self._dispatch_enter(enters_to_send, log_callback)

        if exits_to_send:
            self._dispatch_exit(exits_to_send, log_callback)

    def _ensure_chat_id(self, token: str, log_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """Đảm bảo có Chat ID. Nếu chưa có, tự động dò tìm từ Bot Token qua getUpdates."""
        cid = self.config.chat_id.strip()
        if cid:
            return cid

        ok_det, c_info, msg = auto_detect_chat(token)
        if ok_det and c_info and c_info.get("chat_id"):
            found_cid = c_info["chat_id"]
            self.config.save(
                chat_id=found_cid,
                chat_title=c_info.get("title", ""),
                bot_username=c_info.get("bot_username", "")
            )
            if log_callback:
                log_callback(f"📱 [Telegram] Tự động kết nối với chat: {c_info.get('title', found_cid)}")
            return found_cid

        if log_callback:
            log_callback(f"⚠️ [Telegram] Chưa nhận diện được người nhận từ Bot Token: {msg}")
        return None

    def _dispatch_enter(self, names: List[str], log_callback: Optional[Callable[[str], None]] = None) -> None:
        if not self.config.enabled or not self.config.notify_enter:
            return
        token = self.config.bot_token.strip()
        if not token:
            return

        now_str = datetime.now().strftime("%H:%M:%S")
        joined_raw = ", ".join(names)
        joined_html = ", ".join(f"<b>{n}</b>" for n in names)

        if len(names) == 1:
            text = (
                "🪞 <b>[MEGAMU - DOUBLE GOER]</b>\n"
                f"🎉 Nhân vật {joined_html} đã vào qua cổng Mirror!\n"
                f"⏰ Thời gian: <code>{now_str}</code>"
            )
        else:
            text = (
                "🪞 <b>[MEGAMU - DOUBLE GOER]</b>\n"
                f"🎉 Các nhân vật {joined_html} đã vào qua cổng Mirror!\n"
                f"⏰ Thời gian: <code>{now_str}</code>"
            )

        if log_callback:
            log_callback(f"📱 [Telegram] Báo cáo vào cổng: {joined_raw}")

        self._send_async(token, text, log_callback)

    def _dispatch_exit(self, names: List[str], log_callback: Optional[Callable[[str], None]] = None) -> None:
        if not self.config.enabled or not self.config.notify_exit:
            return
        token = self.config.bot_token.strip()
        if not token:
            return

        now_str = datetime.now().strftime("%H:%M:%S")
        joined_raw = ", ".join(names)
        joined_html = ", ".join(f"<b>{n}</b>" for n in names)

        if len(names) == 1:
            text = (
                "🪞 <b>[MEGAMU - DOUBLE GOER]</b>\n"
                f"🚪 Nhân vật {joined_html} đã thoát ra khỏi Mirror!\n"
                f"⏰ Thời gian: <code>{now_str}</code>"
            )
        else:
            text = (
                "🪞 <b>[MEGAMU - DOUBLE GOER]</b>\n"
                f"🚪 Các nhân vật {joined_html} đã thoát ra khỏi Mirror!\n"
                f"⏰ Thời gian: <code>{now_str}</code>"
            )

        if log_callback:
            log_callback(f"📱 [Telegram] Báo cáo thoát ra: {joined_raw}")

        self._send_async(token, text, log_callback)

    def _send_async(self, token: str, text: str,
                    log_callback: Optional[Callable[[str], None]] = None) -> None:
        def _worker():
            cid = self._ensure_chat_id(token, log_callback)
            if not cid:
                return
            ok, msg = send_telegram_raw(token, cid, text)
            if not ok and ("chat not found" in msg.lower() or "bad request" in msg.lower()):
                # Tự động phục hồi nếu chat_id cũ bị lỗi/không tồn tại
                self.config.chat_id = ""
                cid2 = self._ensure_chat_id(token, log_callback)
                if cid2 and cid2 != cid:
                    ok, msg = send_telegram_raw(token, cid2, text)
            if not ok and log_callback:
                log_callback(f"⚠️ [Telegram Error] {msg}")

        threading.Thread(target=_worker, daemon=True).start()
