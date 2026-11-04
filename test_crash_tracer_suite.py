"""
Test suite for meg_crash_tracer.py
Verifies universal thread exception trapping, formatting, disk logging, and UI dispatching.
"""

import os
import sys
import time
import threading
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from meg_crash_tracer import (
    install_global_exception_hooks,
    register_ui_exception_callback,
    unregister_ui_exception_callback,
    log_thread_exception,
    traced_thread_scope,
    traced_thread,
    CRASH_TRACE_LOG_FILE,
    APP_EXCEPTIONS_LOG_FILE
)

ui_messages = []

def sample_ui_callback(msg: str, level: str = "INFO"):
    ui_messages.append((msg, level))

def run_tests():
    print("=== STARTING MEG CRASH TRACER AUDIT ===")
    
    # Register UI callback
    install_global_exception_hooks(ui_callback=sample_ui_callback)
    
    # Test 1: Direct log_thread_exception
    print("\n--- Test 1: Direct log_thread_exception ---")
    try:
        def failing_function_level_2():
            raise ValueError("Direct test failure message in level 2")
        def failing_function_level_1():
            failing_function_level_2()
        failing_function_level_1()
    except Exception as exc:
        log_thread_exception(
            source="TestRunner.Direct",
            exc=exc,
            thread_name="Slot 02 - Worker",
            details="Testing slot 2 direct exception"
        )
    
    assert len(ui_messages) >= 1, "UI callback was not called"
    last_msg, level = ui_messages[-1]
    print(f"UI Message 1: {last_msg} (level={level})")
    assert "[Slot 02]" in last_msg, f"Expected [Slot 02] prefix in {last_msg}"
    assert "ValueError" in last_msg
    assert "failing_function_level_2" in last_msg
    print("Test 1 PASS!")
    
    # Test 2: Unhandled exception in a spawned background thread
    print("\n--- Test 2: Unhandled exception in spawned thread ---")
    ui_messages.clear()
    
    def unhandled_worker():
        time.sleep(0.05)
        # Simulate null pointer / attribute error
        data = None
        data["dummy_key"] = 123
        
    t = threading.Thread(target=unhandled_worker, name="Slot 05 - AutoMirror", daemon=True)
    t.start()
    t.join(timeout=1.0)
    
    time.sleep(0.1) # allow hook to execute
    assert len(ui_messages) >= 1, "Thread unhandled exception was not dispatched to UI"
    last_msg, level = ui_messages[-1]
    print(f"UI Message 2: {last_msg} (level={level})")
    assert "[Slot 05]" in last_msg, f"Expected [Slot 05] in {last_msg}"
    assert "TypeError" in last_msg
    print("Test 2 PASS!")
    
    # Test 3: Chained exception (raise ... from ...)
    print("\n--- Test 3: Chained Exception ---")
    ui_messages.clear()
    try:
        try:
            x = 1 / 0
        except ZeroDivisionError as zerr:
            raise RuntimeError("Higher level calculation failed") from zerr
    except Exception as exc:
        log_thread_exception("TestChained", exc, thread_name="Slot07_ChainedTest")
        
    assert len(ui_messages) >= 1
    print(f"UI Message 3: {ui_messages[-1][0]}")
    assert "[Slot 07]" in ui_messages[-1][0]
    print("Test 3 PASS!")
    
    # Test 4: traced_thread_scope context manager
    print("\n--- Test 4: traced_thread_scope ---")
    ui_messages.clear()
    with traced_thread_scope("ScopeTest", thread_name="Slot 01 - Scope", swallow=True):
        raise KeyError("scope_test_missing_key")
        
    assert len(ui_messages) >= 1
    assert "KeyError" in ui_messages[-1][0]
    print(f"UI Message 4: {ui_messages[-1][0]}")
    print("Test 4 PASS!")
    
    # Test 5: Verify log files exist and contain formatted entries
    print("\n--- Test 5: Verify log file contents ---")
    assert CRASH_TRACE_LOG_FILE.exists(), f"{CRASH_TRACE_LOG_FILE} not found"
    assert APP_EXCEPTIONS_LOG_FILE.exists(), f"{APP_EXCEPTIONS_LOG_FILE} not found"
    
    content_trace = CRASH_TRACE_LOG_FILE.read_text(encoding="utf-8")
    content_exc = APP_EXCEPTIONS_LOG_FILE.read_text(encoding="utf-8")
    
    assert "THREAD EXCEPTION TRACE" in content_trace
    assert "Slot 02 - Worker" in content_trace
    assert "CALL STACK TRACEBACK" in content_trace
    assert "THREAD EXCEPTION TRACE" in content_exc
    print("Test 5 PASS! Both log files contain structured call stack traces.")
    
    print("\n=== ALL CRASH TRACER AUDIT TESTS PASSED (100%) ===")

if __name__ == "__main__":
    run_tests()
