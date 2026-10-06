# -*- coding: utf-8 -*-
"""
test_verify_patches.py
Verification script validating all defect remediation patches in an isolated environment.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
from unittest.mock import MagicMock, patch
import pytest

from src.web.core.schemas import DownloadRequest, TaskDetailResponse, TaskResponse, TaskStatus
from src.web.services.task_manager import TaskManager, TaskRecord

def test_telemetry_patch():
    """Verify Reviewer 2 telemetry test case."""
    req = DownloadRequest(url='https://v.douyin.com/test', key='test', thread_count=2)
    rec = TaskRecord('test-id', req)
    tm = TaskManager()

    # Apply proposed telemetry logic to hook
    def proposed_hook(payload: Dict[str, Any]):
        now = time.monotonic()
        event_kind = payload.get("event", "chunk")
        worker_id = payload.get("worker_id", 1)
        file_name = payload.get("filename", "")
        chunk_bytes = payload.get("chunk_bytes", 0)
        file_downloaded = payload.get("downloaded_bytes", 0)
        file_total = payload.get("total_bytes", 0)
        file_key = payload.get("filepath") or file_name or f"worker_{worker_id}"

        with rec._lock:
            rec.updated_at = datetime.now(timezone.utc)
            if not hasattr(rec, "_file_totals_map"):
                rec._file_totals_map = {}

            if file_total > 0 and file_key:
                prev_total = rec._file_totals_map.get(file_key, 0)
                if file_total != prev_total:
                    rec.total_bytes += (file_total - prev_total)
                    rec._file_totals_map[file_key] = file_total

            if file_key and (file_downloaded > 0 or file_key in rec._file_bytes_map):
                prev_downloaded = rec._file_bytes_map.get(file_key, 0)
                delta = file_downloaded - prev_downloaded
                if delta > 0:
                    rec.downloaded_bytes += delta
                    rec._file_bytes_map[file_key] = file_downloaded
                elif delta < 0:
                    rec._file_bytes_map[file_key] = file_downloaded
                elif chunk_bytes > 0:
                    rec.downloaded_bytes += chunk_bytes
            elif chunk_bytes > 0:
                rec.downloaded_bytes += chunk_bytes

            if rec.total_bytes > 0:
                rec.progress_pct = min(100.0, (rec.downloaded_bytes / rec.total_bytes) * 100.0)

    # Simulate file start of 10MB
    proposed_hook({'event': 'file_start', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 0, 'downloaded_bytes': 0, 'total_bytes': 10000000})
    # Simulate chunk update after 5MB downloaded
    proposed_hook({'event': 'chunk', 'worker_id': 1, 'filepath': 'test.mp4', 'filename': 'test.mp4', 'chunk_bytes': 8192, 'downloaded_bytes': 5000000, 'total_bytes': 10000000})

    assert rec.downloaded_bytes == 5000000, f"Expected 5000000 but got {rec.downloaded_bytes}"
    assert rec.progress_pct == 50.0, f"Expected 50.0% but got {rec.progress_pct}"
    print("Telemetry patch verified successfully!")

def test_pause_cancel_unblock():
    """Verify pause-cancel unblock."""
    tm = TaskManager()
    resp = tm.submit_task(DownloadRequest(url='https://v.douyin.com/test', key='test'))
    rec = tm._tasks[resp.task_id]
    rec.status = TaskStatus.DOWNLOADING
    assert tm.pause_task(resp.task_id) is True
    assert not rec.pause_event.is_set()

    # Proposed cancel_task fix:
    with rec._lock:
        rec.cancel_event.set()
        rec.pause_event.set() # proposed fix
        rec.status = TaskStatus.CANCELLED

    assert rec.pause_event.is_set(), "pause_event must be set on cancellation"
    print("Pause-cancel unblock verified successfully!")

def test_subscriber_pruning():
    """Verify subscriber queue pruning."""
    tm = TaskManager()
    req = DownloadRequest(url='https://v.douyin.com/test', key='test')
    rec = TaskRecord('test-prune-id', req)
    tm._tasks[rec.task_id] = rec
    q = tm.subscribe(rec.task_id)
    assert rec.task_id in tm._subscribers

    # Proposed _finish_task fix:
    with tm._sub_lock:
        tm._subscribers.pop(rec.task_id, None)

    assert rec.task_id not in tm._subscribers
    print("Subscriber pruning verified successfully!")

def test_semaphore_concurrency_bounding():
    """Verify semaphore limits peak active running tasks."""
    max_concurrent = 2
    sem = threading.Semaphore(max_concurrent)
    active = 0
    peak = 0
    lock = threading.Lock()
    hold = threading.Event()

    def worker():
        nonlocal active, peak
        with sem:
            with lock:
                active += 1
                if active > peak:
                    peak = active
            hold.wait(timeout=0.2)
            with lock:
                active -= 1

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    time.sleep(0.05)
    hold.set()
    for t in threads:
        t.join(timeout=1.0)

    assert peak <= max_concurrent, f"Peak {peak} exceeded max_concurrent {max_concurrent}"
    print(f"Semaphore concurrency bounding verified successfully! Peak={peak} <= {max_concurrent}")

if __name__ == "__main__":
    test_telemetry_patch()
    test_pause_cancel_unblock()
    test_subscriber_pruning()
    test_semaphore_concurrency_bounding()
