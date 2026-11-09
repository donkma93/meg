# -*- coding: utf-8 -*-
"""
test_telegram_mirror.py
Kiểm tra chức năng lưu/nạp cấu hình Telegram, cơ chế lọc trạng thái và gom nhóm debounce báo cáo Mirror.
"""

import time
import unittest
from pathlib import Path
from telegram_notifier import (
    TelegramConfig,
    MirrorTelegramNotifier,
    send_telegram_raw,
    test_telegram_connection,
    TELEGRAM_CONFIG_FILE,
    MIRROR_CONFIG_FILE
)


class TestTelegramMirror(unittest.TestCase):

    def setUp(self):
        # Backup config nếu có
        self.backup = None
        if TELEGRAM_CONFIG_FILE.exists():
            self.backup = TELEGRAM_CONFIG_FILE.read_text(encoding="utf-8")
        self.mirror_backup = None
        if MIRROR_CONFIG_FILE.exists():
            self.mirror_backup = MIRROR_CONFIG_FILE.read_text(encoding="utf-8")

    def tearDown(self):
        # Khôi phục config
        if self.backup is not None:
            TELEGRAM_CONFIG_FILE.write_text(self.backup, encoding="utf-8")
        elif TELEGRAM_CONFIG_FILE.exists():
            try:
                TELEGRAM_CONFIG_FILE.unlink()
            except Exception:
                pass
        if self.mirror_backup is not None:
            MIRROR_CONFIG_FILE.write_text(self.mirror_backup, encoding="utf-8")

    def test_01_config_save_and_load(self):
        cfg = TelegramConfig()
        cfg.save(bot_token="123456:ABC-DEF", chat_id="987654321", enabled=True, notify_enter=True, notify_exit=False)

        cfg2 = TelegramConfig()
        self.assertEqual(cfg2.bot_token, "123456:ABC-DEF")
        self.assertEqual(cfg2.chat_id, "987654321")
        self.assertTrue(cfg2.enabled)
        self.assertTrue(cfg2.notify_enter)
        self.assertFalse(cfg2.notify_exit)
        print("Test 1: Config save & load passed.")

    def test_02_notifier_state_transitions_and_debounce(self):
        cfg = TelegramConfig()
        cfg.save(bot_token="dummy_token", chat_id="123456", enabled=True, notify_enter=True, notify_exit=True)

        notifier = MirrorTelegramNotifier(config=cfg)

        # Giả lập ghi nhận: ban đầu 3 tài khoản ở ngoài map
        notifier.record_character_state("HeroA", slot_idx=1, is_connected=True, is_in_mirror=False)
        notifier.record_character_state("HeroB", slot_idx=2, is_connected=True, is_in_mirror=False)
        notifier.record_character_state("HeroC", slot_idx=3, is_connected=True, is_in_mirror=False)

        # Chưa có ai vào cổng
        self.assertEqual(len(notifier._pending_enters), 0)

        # Đến giờ :10, cả 3 tài khoản cùng vào cổng Mirror!
        notifier.record_character_state("HeroA", slot_idx=1, is_connected=True, is_in_mirror=True)
        notifier.record_character_state("HeroB", slot_idx=2, is_connected=True, is_in_mirror=True)
        notifier.record_character_state("HeroC", slot_idx=3, is_connected=True, is_in_mirror=True)

        # Cả 3 phải nằm trong hàng đợi gom nhóm _pending_enters
        self.assertEqual(notifier._pending_enters, ["HeroA", "HeroB", "HeroC"])
        self.assertIsNotNone(notifier._enter_timer)

        # Giả lập tua thời gian timer để test flush
        notifier._enter_timer = time.time() - 3.0

        logs = []
        sent_messages = []

        def fake_send(token, text, log_cb=None):
            sent_messages.append(text)

        notifier._send_async = fake_send
        notifier.check_and_flush(log_callback=lambda m: logs.append(m))

        self.assertEqual(len(notifier._pending_enters), 0)
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("Các nhân vật <b>HeroA</b>, <b>HeroB</b>, <b>HeroC</b> đã vào qua cổng Mirror!", sent_messages[0])
        print("Test 2A: Enter debounce batching passed.")

        # Test thoái lui (Hysteresis check): 1 nhịp False chưa vội báo thoát
        notifier.record_character_state("HeroA", slot_idx=1, is_connected=True, is_in_mirror=False)
        self.assertEqual(len(notifier._pending_exits), 0)  # Chưa đủ 2 nhịp

        # Nhịp False thứ 2 -> xác nhận thoát ra!
        notifier.record_character_state("HeroA", slot_idx=1, is_connected=True, is_in_mirror=False)
        self.assertEqual(notifier._pending_exits, ["HeroA"])

        # HeroB cũng thoát ra
        notifier.record_character_state("HeroB", slot_idx=2, is_connected=True, is_in_mirror=False)
        notifier.record_character_state("HeroB", slot_idx=2, is_connected=True, is_in_mirror=False)
        self.assertEqual(notifier._pending_exits, ["HeroA", "HeroB"])

        notifier._exit_timer = time.time() - 3.0
        sent_messages.clear()
        notifier.check_and_flush(log_callback=lambda m: logs.append(m))

        self.assertEqual(len(notifier._pending_exits), 0)
        self.assertEqual(len(sent_messages), 1)
        self.assertNotIn("<b>HeroC</b>", sent_messages[0])
        self.assertIn("Các nhân vật <b>HeroA</b>, <b>HeroB</b> đã thoát ra khỏi Mirror!", sent_messages[0])
        print("Test 2B: Exit hysteresis & batching passed.")

    def test_03_invalid_credentials_handling(self):
        # Kiểm tra token rỗng
        ok, msg = send_telegram_raw("", "123", "test")
        self.assertFalse(ok)
        self.assertIn("Bot Token", msg)

        # Kiểm tra chat id rỗng
        ok, msg = send_telegram_raw("123:ABC", "", "test")
        self.assertFalse(ok)
        self.assertIn("Chat ID", msg)
        print("Test 3: Empty validation passed.")

    def test_04_auto_detect_chat_resolution(self):
        from telegram_notifier import extract_chat_from_update

        sample_update = {
            "update_id": 999,
            "message": {
                "message_id": 1,
                "from": {"id": 112233, "first_name": "Don", "username": "donkma"},
                "chat": {"id": 112233, "first_name": "Don", "username": "donkma", "type": "private"},
                "text": "/start"
            }
        }
        chat = extract_chat_from_update(sample_update)
        self.assertIsNotNone(chat)
        self.assertEqual(chat["id"], 112233)
        self.assertEqual(chat["first_name"], "Don")

        # Kiểm tra Notifier tự động dò tìm chat khi ban đầu chưa có chat_id
        cfg = TelegramConfig()
        cfg.save(bot_token="test_token_123", chat_id="", enabled=True)
        notifier = MirrorTelegramNotifier(config=cfg)

        # Mock auto_detect_chat
        import telegram_notifier
        orig_detect = telegram_notifier.auto_detect_chat
        telegram_notifier.auto_detect_chat = lambda tok, timeout=8.0: (
            True,
            {"chat_id": "112233", "title": "Don", "bot_username": "my_test_bot"},
            "OK"
        )
        try:
            resolved_cid = notifier._ensure_chat_id("test_token_123")
            self.assertEqual(resolved_cid, "112233")
            self.assertEqual(notifier.config.chat_id, "112233")
            self.assertEqual(notifier.config.chat_title, "Don")
        finally:
            telegram_notifier.auto_detect_chat = orig_detect

        print("Test 4: Auto-detect chat resolution passed.")


if __name__ == "__main__":
    unittest.main()
