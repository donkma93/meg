"""
Unit tests for core.logger: AsyncRingBufferLogger, bounded memory, and rotation.
"""

import sys
import time
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.logger import AsyncRingBufferLogger, LogEntry


class TestAsyncRingBufferLogger(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test_run.log"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_entry_parsing(self):
        e1 = LogEntry("[Slot 03] Auto train started", level="info")
        self.assertEqual(e1.slot_tag, "03")
        self.assertEqual(e1.level, "INFO")
        self.assertIn("Auto train started", e1.full_formatted)

        e2 = LogEntry("Global system initialized", level="success")
        self.assertEqual(e2.slot_tag, "ALL")
        self.assertEqual(e2.level, "SUCCESS")

    def test_bounded_ring_buffer(self):
        # Create logger with small capacity 50
        logger = AsyncRingBufferLogger(
            log_file=self.log_file,
            ring_capacity=50,
            max_bytes=1024 * 1024,
            backup_count=2
        )
        try:
            # Push 200 logs
            for i in range(200):
                logger.log(f"Log message {i}", level="INFO")

            tuples = logger.get_logs_data_tuples()
            # Must strictly have at most 50 items
            self.assertEqual(len(tuples), 50)
            # The newest log must be present
            self.assertIn("Log message 199", tuples[-1][2])
            # Old logs must have been evicted (Zero RAM leak)
            self.assertNotIn("Log message 0", [t[2] for t in tuples])

        finally:
            logger.shutdown()

    def test_slot_filtering(self):
        logger = AsyncRingBufferLogger(
            log_file=self.log_file,
            ring_capacity=100
        )
        try:
            logger.log("[Slot 01] Slot 1 action", level="INFO")
            logger.log("[Slot 02] Slot 2 action", level="INFO")
            logger.log("[Slot 01] Slot 1 second action", level="INFO")
            logger.log("General system notice", level="INFO")

            s1_logs = logger.get_filtered_lines(filter_slot="01")
            self.assertEqual(len(s1_logs), 2)
            self.assertTrue(all("Slot 01" in line for line in s1_logs))

            s2_logs = logger.get_filtered_lines(filter_slot="02")
            self.assertEqual(len(s2_logs), 1)

            all_logs = logger.get_filtered_lines(filter_slot="ALL")
            self.assertEqual(len(all_logs), 4)

        finally:
            logger.shutdown()

    def test_async_disk_writing(self):
        logger = AsyncRingBufferLogger(
            log_file=self.log_file,
            ring_capacity=100
        )
        try:
            for i in range(25):
                logger.log(f"Test batch message {i}")

            # Shutdown flushes disk writer
            logger.shutdown()

            self.assertTrue(self.log_file.exists())
            content = self.log_file.read_text(encoding="utf-8")
            self.assertIn("Test batch message 0", content)
            self.assertIn("Test batch message 24", content)

        except Exception as e:
            logger.shutdown()
            raise e

    def test_log_rotation(self):
        # Set max_bytes very small (300 bytes) to trigger rotation
        logger = AsyncRingBufferLogger(
            log_file=self.log_file,
            ring_capacity=100,
            max_bytes=300,
            backup_count=2
        )
        try:
            # Batch 1: exceed 300 bytes
            for i in range(25):
                logger.log(f"First batch message {i:03d}")
            time.sleep(1.2)  # Wait for batch 1 to flush to disk

            # Batch 2: triggers rotation of batch 1 to .1 and writes into new log_file
            for i in range(25):
                logger.log(f"Second batch message {i:03d}")
            time.sleep(1.2)  # Wait for batch 2 to flush to disk
            logger.shutdown()

            # Check if rotated backup file exists and current log_file exists
            backup_1 = self.log_file.with_name(f"{self.log_file.name}.1")
            self.assertTrue(self.log_file.exists())
            self.assertTrue(backup_1.exists())

        except Exception as e:
            logger.shutdown()
            raise e


if __name__ == "__main__":
    unittest.main()
