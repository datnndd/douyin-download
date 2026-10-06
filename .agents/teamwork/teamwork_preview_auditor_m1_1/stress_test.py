# -*- coding: utf-8 -*-
"""
Forensic Auditor Adversarial Stress Test Suite for Milestone 1.
Validates concurrency, edge cases, error resilience, and lack of facades.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.web.core.config import ConfigManager, load_config_file, save_config_file, parse_raw_cookie, format_cookie_dict
from src.web.core.schemas import DownloadRequest, SettingsModel, TaskStatus, KeyType
from src.web.services.douyin_service import DouyinService, DouyinInvalidUrlError, DouyinNotFoundError
from src.web.services.task_manager import TaskManager, TaskRecord
from src.douyin.download import Download

def test_config_concurrency():
    print("[1/5] Testing ConfigManager concurrent stress...")
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.yaml"
        initial_yaml = "path: ./Downloaded/\nthread: 5\ncookies:\n  token: init\n"
        cfg_path.write_text(initial_yaml, encoding="utf-8")

        ConfigManager._instance = None
        manager = ConfigManager.get_instance(cfg_path)

        def worker(idx):
            for i in range(10):
                s = manager.get_settings()
                s.thread = (idx * 10 + i) % 16 + 1
                s.raw_cookie = f"token_{idx}={i}; ttwid={idx}_{i}"
                manager.update_settings(s)
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify final file is intact, valid yaml, and non-empty
        final_content = cfg_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(final_content)
        assert isinstance(parsed, dict)
        assert "thread" in parsed
        assert "cookies" in parsed or "cookie" in parsed
    print("  -> PASSED: ConfigManager survived multi-threaded concurrent mutations.")

def test_url_adversarial_inputs():
    print("[2/5] Testing DouyinService adversarial URL inputs...")
    service = DouyinService()

    # Empty / whitespace
    for bad_input in ["", "   ", "\n\t", "no url at all", "ftp://example.com"]:
        try:
            service.sync_parse_url(bad_input)
            assert False, f"Should have failed on: {bad_input}"
        except DouyinInvalidUrlError:
            pass

    # Decorated clipboard inputs
    clipboard_cases = [
        ("【测试视频】 https://v.douyin.com/abc123/ 复制打开抖音", "https://v.douyin.com/abc123/"),
        ("Check this: https://www.douyin.com/video/7488893440932039970?extra=1, nice!", "https://www.douyin.com/video/7488893440932039970?extra=1"),
        ("Multiple links: https://v.douyin.com/first/ and https://v.douyin.com/second/", "https://v.douyin.com/first/"),
    ]
    for text, expected in clipboard_cases:
        extracted = service.extract_share_url(text)
        assert extracted == expected, f"Expected {expected}, got {extracted}"

    print("  -> PASSED: DouyinService correctly sanitized and extracted URLs.")

def test_task_manager_mass_concurrency():
    print("[3/5] Testing TaskManager mass task submission & lifecycle...")
    manager = TaskManager(max_concurrent_tasks=4, max_total_workers=8)
    
    # Submit 25 tasks rapidly
    task_ids = []
    for i in range(25):
        req = DownloadRequest(
            url=f"https://www.douyin.com/video/74888934409320399{i:02d}",
            key_type="aweme",
            key=f"74888934409320399{i:02d}",
            thread_count=2,
        )
        resp = manager.submit_task(req)
        task_ids.append(resp.task_id)

    assert len(manager.list_tasks()) >= 25

    # Cancel half of them immediately
    for tid in task_ids[:12]:
        manager.cancel_task(tid)

    # Check states
    cancelled_count = len(manager.list_tasks(status=TaskStatus.CANCELLED))
    assert cancelled_count >= 12, f"Expected >= 12 cancelled, got {cancelled_count}"

    print("  -> PASSED: TaskManager handled 25 concurrent tasks and selective abort tokens.")

def test_sse_queue_lifecycle():
    print("[4/5] Testing SSE subscriber queue lifecycle and cleanup...")
    async def _test():
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        loop = asyncio.get_running_loop()
        manager.set_event_loop(loop)

        # Global subscribe
        q_global = manager.subscribe()
        assert len(manager._global_subscribers) == 1

        # Task-specific subscribe
        q_task = manager.subscribe(task_id="task-x")
        assert len(manager._subscribers.get("task-x", set())) == 1

        # Unsubscribe
        manager.unsubscribe(q_global)
        assert len(manager._global_subscribers) == 0

        manager.unsubscribe(q_task, task_id="task-x")
        assert "task-x" not in manager._subscribers
    
    asyncio.run(_test())
    print("  -> PASSED: SSE queue subscription & garbage collection fully functional.")

def test_download_cancellation_during_retry():
    print("[5/5] Testing Download cancellation responsiveness during retry wait...")
    cancel = threading.Event()
    d = Download(cancel_event=cancel)
    
    start_time = time.time()
    # Trigger cancel after 100ms
    def cancel_later():
        time.sleep(0.1)
        cancel.set()
    
    t = threading.Thread(target=cancel_later)
    t.start()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        res = d.download_with_resume("https://invalid-host-404-unreachable.example.com/v.mp4", Path(tmpdir) / "test.mp4", "test")
        elapsed = time.time() - start_time
        assert res is False
        # If cancellation wait wasn't responsive, retry loop would take min 2 + 4 + 8 + ... seconds!
        assert elapsed < 3.0, f"Cancellation took too long: {elapsed:.2f}s"
    
    t.join()
    print("  -> PASSED: Download cancellation interrupted retry backoff promptly.")

if __name__ == "__main__":
    test_config_concurrency()
    test_url_adversarial_inputs()
    test_task_manager_mass_concurrency()
    test_sse_queue_lifecycle()
    test_download_cancellation_during_retry()
    print("\nALL 5 FORENSIC STRESS TESTS PASSED SUCCESSFULLY.")
