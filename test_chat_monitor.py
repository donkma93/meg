#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEGAMU In-Game Chat Monitor & Logger (Thử Nghiệm)
==================================================
Tự động gắn vào tiến trình MEGAMU qua Frida Dynamic Instrumentation,
bắt sự kiện và hiển thị toàn bộ nội dung chat trong game theo thời gian thực:
- Kênh Chat: Whisper, Party, Guild, Family/Gens, System, General, Post, Lệnh gửi đi.
- Lọc bỏ thẻ màu Unity RichText, highlight màu sắc trực quan trên Terminal.
- Tự động ghi chép lịch sử chat vào tệp `chat_history.log`.
- An toàn tuyệt đối: 100% không ghi đè mã nguồn, hỗ trợ Detach sạch khi ấn Ctrl+C.
"""

import os
import sys
import time
import re
import json
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import frida
except ImportError:
    print("[ERROR] Thư viện frida chưa được cài đặt! Hãy chạy: pip install frida")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("[ERROR] Thư viện psutil chưa được cài đặt! Hãy chạy: pip install psutil")
    sys.exit(1)

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    class Fore:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        DIM = NORMAL = BRIGHT = RESET_ALL = ""

LOG_FILE = "chat_history.log"

FRIDA_CHAT_JS = r"""
'use strict';

var mod = Process.findModuleByName('GameAssembly.dll');
if (!mod) {
    send({ type: 'log', message: 'GameAssembly.dll không tìm thấy trong tiến trình!' });
} else {
    var baseAddr = mod.base;
    send({ type: 'log', message: 'Đã tìm thấy GameAssembly.dll tại: ' + baseAddr });

    function readIl2CppString(p) {
        if (!p || p.isNull()) return "";
        try {
            var len = p.add(0x10).readS32();
            if (len <= 0 || len > 2000) return "";
            return p.add(0x14).readUtf16String(len);
        } catch (e) {
            return "";
        }
    }

    // 1. Hook ChatFrame.HIDIFIPDINE (0x1321200)
    // Signature: void HIDIFIPDINE(ChatFrame* this, int channel, string text, string sender)
    // Channel: 0: General, 1: Party, 2: Guild, 3: Whisper, 4: System, 5: Family
    try {
        var rva_hidif = ptr('0x1321200');
        Interceptor.attach(baseAddr.add(rva_hidif), {
            onEnter: function(args) {
                try {
                    var chan = args[1].toInt32();
                    var text = readIl2CppString(args[2]);
                    var sender = readIl2CppString(args[3]);
                    if (text && text.length > 0) {
                        send({
                            type: 'chat_event',
                            source: 'HIDIFIPDINE',
                            channel: chan,
                            sender: sender,
                            text: text
                        });
                    }
                } catch (err) {}
            }
        });
        send({ type: 'log', message: 'Hook 1 OK: ChatFrame.HIDIFIPDINE (0x1321200) - Phân loại kênh chat' });
    } catch (e) {
        send({ type: 'log', message: 'Lỗi hook HIDIFIPDINE: ' + e.message });
    }

    // 2. Hook ChatFrame.OKOKBFICDBE (0x1321130)
    // Signature: void OKOKBFICDBE(ChatFrame* this, string name, string text)
    try {
        var rva_okok = ptr('0x1321130');
        Interceptor.attach(baseAddr.add(rva_okok), {
            onEnter: function(args) {
                try {
                    var name = readIl2CppString(args[1]);
                    var text = readIl2CppString(args[2]);
                    if (text && text.length > 0) {
                        send({
                            type: 'chat_event',
                            source: 'OKOKBFICDBE',
                            channel: -1,
                            sender: name,
                            text: text
                        });
                    }
                } catch (err) {}
            }
        });
        send({ type: 'log', message: 'Hook 2 OK: ChatFrame.OKOKBFICDBE (0x1321130) - Bắt tin nhắn theo tên' });
    } catch (e) {}

    // 3. Hook ChatFrame.FHIJKOEKEEJ (0x1322C60)
    // Signature: void FHIJKOEKEEJ(ChatFrame* this, int type, string text)
    try {
        var rva_fhij = ptr('0x1322C60');
        Interceptor.attach(baseAddr.add(rva_fhij), {
            onEnter: function(args) {
                try {
                    var text = readIl2CppString(args[2]);
                    if (text && text.length > 0) {
                        send({
                            type: 'chat_event',
                            source: 'SYSTEM_EVENT',
                            channel: 4,
                            sender: 'HỆ THỐNG',
                            text: text
                        });
                    }
                } catch (err) {}
            }
        });
        send({ type: 'log', message: 'Hook 3 OK: ChatFrame.FHIJKOEKEEJ (0x1322C60) - Thông báo hệ thống' });
    } catch (e) {}

    // 4. Hook Outgoing Chat: Mega.Chat.FCIBNHIHDHO (0xF95530)
    // Signature: static void FCIBNHIHDHO(string text)
    try {
        var rva_send = ptr('0xF95530');
        Interceptor.attach(baseAddr.add(rva_send), {
            onEnter: function(args) {
                try {
                    var text = readIl2CppString(args[0]);
                    if (text && text.length > 0) {
                        send({
                            type: 'chat_event',
                            source: 'OUTGOING',
                            channel: 99,
                            sender: 'BẢN THÂN',
                            text: text
                        });
                    }
                } catch (err) {}
            }
        });
        send({ type: 'log', message: 'Hook 4 OK: Mega.Chat.GửiChat (0xF95530) - Lắng nghe tin gõ gửi đi' });
    } catch (e) {}

    // 5. Hook CommandManager.BDMGLHEGJHO (0xFA0A60)
    // Signature: bool BDMGLHEGJHO(string command)
    try {
        var rva_cmd = ptr('0xFA0A60');
        Interceptor.attach(baseAddr.add(rva_cmd), {
            onEnter: function(args) {
                try {
                    var cmd = readIl2CppString(args[0]);
                    if (cmd && cmd.length > 0) {
                        send({
                            type: 'chat_event',
                            source: 'COMMAND',
                            channel: 99,
                            sender: 'LỆNH GỬI',
                            text: cmd
                        });
                    }
                } catch (err) {}
            }
        });
        send({ type: 'log', message: 'Hook 5 OK: CommandManager.Lệnh (0xFA0A60) - Lắng nghe lệnh /' });
    } catch (e) {}
}
"""

CHANNEL_MAP = {
    0: ("GENERAL", Fore.WHITE, Style.BRIGHT),
    1: ("PARTY", Fore.CYAN, Style.BRIGHT),
    2: ("GUILD", Fore.YELLOW, Style.BRIGHT),
    3: ("WHISPER", Fore.MAGENTA, Style.BRIGHT),
    4: ("SYSTEM", Fore.RED, Style.BRIGHT),
    5: ("FAMILY", Fore.GREEN, Style.BRIGHT),
    99: ("OUTGOING", Fore.BLUE, Style.BRIGHT),
}

def clean_rich_text(text: str) -> str:
    """Xóa các thẻ màu và định dạng Unity RichText: <color=...>, </color>, <b>, </b>..."""
    if not text:
        return ""
    cleaned = re.sub(r'<color=[^>]+>', '', text, flags=re.IGNORECASE)
    cleaned = re.sub(r'</color>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<size=[^>]+>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</size>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</?[bi]>', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def detect_channel_from_text(raw_text: str, default_ch: int) -> int:
    """Tự động phân tích kênh nếu tin nhắn chứa tag như [Whisper], [Party], [Guild]..."""
    lower = raw_text.lower()
    if "[whisper]" in lower or "whisper" in lower:
        return 3
    if "[party]" in lower:
        return 1
    if "[guild]" in lower or "[alliance]" in lower:
        return 2
    if "[family]" in lower:
        return 5
    if "[system]" in lower or "[status]" in lower or "victory!" in lower:
        return 4
    if "/post" in lower or "[post]" in lower:
        return 2  # hiển thị nổi bật như guild/post
    return default_ch if default_ch >= 0 else 0


class ChatMonitorApp:
    def __init__(self, pid: int):
        self.pid = pid
        self.session: Optional[frida.core.Session] = None
        self.script: Optional[frida.core.Script] = None
        self.running = True
        self.recent_messages: List[str] = []
        self._lock = threading.Lock()

    def _is_duplicate(self, key: str) -> bool:
        with self._lock:
            if key in self.recent_messages:
                return True
            self.recent_messages.append(key)
            if len(self.recent_messages) > 100:
                self.recent_messages.pop(0)
            return False

    def on_message(self, message: Dict[str, Any], data: Any):
        try:
            mtype = message.get("type")
            if mtype == "send":
                payload = message.get("payload")
                if isinstance(payload, dict):
                    ptype = payload.get("type")
                    if ptype == "log":
                        print(f"{Fore.BLACK}{Style.BRIGHT}[ENGINE] {payload.get('message')}{Style.RESET_ALL}")
                    elif ptype == "chat_event":
                        self.handle_chat_event(payload)
            elif mtype == "error":
                print(f"{Fore.RED}[FRIDA ERROR] {message.get('description')}{Style.RESET_ALL}")
        except Exception as e:
            pass

    def handle_chat_event(self, event: Dict[str, Any]):
        raw_text = event.get("text", "")
        raw_sender = event.get("sender", "")
        ch_id = event.get("channel", -1)

        cleaned_text = clean_rich_text(raw_text)
        cleaned_sender = clean_rich_text(raw_sender)

        if not cleaned_text:
            return

        # Xác định kênh chat chuẩn
        resolved_ch = detect_channel_from_text(raw_text, ch_id)

        # Chống trùng lặp (tránh 2 hook cùng bắt 1 tin)
        dedup_key = f"{resolved_ch}:{cleaned_sender}:{cleaned_text}"
        if self._is_duplicate(dedup_key):
            return

        ch_name, ch_color, ch_style = CHANNEL_MAP.get(
            resolved_ch, ("UNKNOWN", Fore.WHITE, Style.NORMAL)
        )

        now_str = datetime.now().strftime("%H:%M:%S")

        # Định dạng xuất ra màn hình
        sender_part = f"<{cleaned_sender}>: " if cleaned_sender else ""
        formatted_line = (
            f"{Fore.BLACK}{Style.BRIGHT}[{now_str}]{Style.RESET_ALL} "
            f"{ch_color}{ch_style}[{ch_name:^7}]{Style.RESET_ALL} "
            f"{Fore.LIGHTWHITE_EX}{sender_part}{cleaned_text}{Style.RESET_ALL}"
        )
        print(formatted_line)

        # Ghi log file
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{now_str}] [{ch_name}] {sender_part}{cleaned_text}\n")
        except Exception:
            pass

    def start(self):
        print(f"\n{Fore.GREEN}{Style.BRIGHT}======================================================{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{Style.BRIGHT}🚀 ĐANG KẾT NỐI VÀO TIẾN TRÌNH MEGAMU (PID {self.pid})...{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{Style.BRIGHT}======================================================{Style.RESET_ALL}")

        try:
            self.session = frida.attach(self.pid)
            self.script = self.session.create_script(FRIDA_CHAT_JS)
            self.script.on("message", self.on_message)
            self.script.load()

            print(f"{Fore.GREEN}✔ Đã kích hoạt Chat Monitor thành công!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}💡 Hãy vào game gõ chat, mật thư, hoặc chờ người khác chat để kiểm tra.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}📋 Nhật ký chat đang được lưu đồng thời vào: {LOG_FILE}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}🛑 Nhấn Ctrl + C bất kỳ lúc nào để ngắt kết nối an toàn.{Style.RESET_ALL}\n")

            while self.running:
                time.sleep(0.5)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Đang ngắt kết nối an toàn khỏi tiến trình MEGAMU...{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[LỖI] Không thể attach vào PID {self.pid}: {e}{Style.RESET_ALL}")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.script:
            try:
                self.script.unload()
            except Exception:
                pass
            self.script = None
        if self.session:
            try:
                self.session.detach()
            except Exception:
                pass
            self.session = None
        print(f"{Fore.GREEN}✔ Đã Detach hoàn tất. Chương trình dừng an toàn.{Style.RESET_ALL}")


def find_megamu_pids() -> List[int]:
    """Tìm tất cả PID tiến trình MEGAMU.exe đang chạy."""
    pids = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = (p.info.get('name') or '').lower()
            if name in ('megamu.exe', 'megamu'):
                pids.append(p.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids


def main():
    pids = find_megamu_pids()
    if not pids:
        print(f"{Fore.RED}[THÔNG BÁO] Hiện tại không có tiến trình MEGAMU.exe nào đang chạy trên máy!{Style.RESET_ALL}")
        print("Vui lòng mở game MEGAMU trước, sau đó chạy lại script này.")
        return

    selected_pid = pids[0]
    if len(pids) > 1:
        print(f"{Fore.CYAN}Tìm thấy {len(pids)} cửa sổ game MEGAMU đang chạy:{Style.RESET_ALL}")
        for idx, pid in enumerate(pids):
            print(f"  [{idx + 1}] MEGAMU PID: {pid}")
        try:
            ans = input(f"\nChọn số thứ tự client muốn theo dõi chat (Mặc định 1): ").strip()
            if ans and ans.isdigit():
                choice = int(ans) - 1
                if 0 <= choice < len(pids):
                    selected_pid = pids[choice]
        except Exception:
            pass

    app = ChatMonitorApp(selected_pid)
    app.start()


if __name__ == "__main__":
    main()
