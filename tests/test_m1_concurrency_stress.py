# -*- coding: utf-8 -*-
"""
tests/test_m1_concurrency_stress.py
Empirical Concurrency and Stress Test Suite for Milestone 1.
Challenger 1: Concurrency & Stress Verification.

Validates:
1. Rapid Concurrent Task Submissions & Bounded Thread Pool
2. Immediate Cancellation Responsiveness & Thread Leak / Zombie Detection
3. High-Frequency Chunk Emission, Throttling Suppression & SSE Queue Bounds
4. Pause and Resume State Transitions & Race Conditions
5. Pause + Cancel Deadlock / Zombie Thread Vulnerability
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gc
from pathlib import Path
import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch
import pytest

from src.web.core.schemas import (
    DownloadProgressEvent,
    DownloadRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskStatus,
)
from src.web.services.task_manager import TaskManager, TaskRecord
from src.douyin.download import Download


class TestConcurrencyStressSuite:
    """Rigorous empirical stress test harness for TaskManager and DownloadEngine."""

    # =========================================================================
    # 1. Rapid Concurrent Task Submissions & Thread Pool Bounds
    # =========================================================================

    def test_rapid_concurrent_task_submissions(self, tmp_path):
        """
        Stress Test 1A: 25 concurrent threads simultaneously submit tasks.
        Verifies:
        - Thread safety of TaskManager._tasks and _task_lock
        - No deadlocks, race conditions, or dropped tasks
        - Every submitted task receives a unique UUID and PENDING status
        """
        manager = TaskManager(max_concurrent_tasks=4, max_total_workers=8)
        num_tasks = 25
        results: List[TaskResponse] = []
        submission_lock = threading.Lock()

        # Mock service that blocks briefly simulating item resolution
        mock_service = MagicMock()
        mock_service.get_download_items.return_value = [
            {"aweme_id": "item_mock", "desc": "test_mock", "awemeType": 0}
        ]

        def submit_worker(idx: int):
            req = DownloadRequest(
                url=f"https://www.douyin.com/video/74888934409320399{idx:02d}",
                key_type="aweme",
                key=f"74888934409320399{idx:02d}",
                download_path=str(tmp_path),
            )
            with patch("src.douyin.download.Download.awemeDownload", return_value=True):
                resp = manager.submit_task(req, douyin_service=mock_service)
                with submission_lock:
                    results.append(resp)

        start_time = time.monotonic()
        threads = [threading.Thread(target=submit_worker, args=(i,)) for i in range(num_tasks)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), "Submission thread timed out / hung!"

        elapsed = time.monotonic() - start_time
        print(f"\n[STRESS 1A] Submitted {num_tasks} concurrent tasks in {elapsed:.4f}s")

        assert len(results) == num_tasks, f"Expected {num_tasks} tasks, got {len(results)}"
        task_ids = {r.task_id for r in results}
        assert len(task_ids) == num_tasks, "Duplicate task IDs detected!"

        # Query all tasks through list_tasks and verify no corrupt entries
        all_tasks = manager.list_tasks()
        assert len(all_tasks) >= num_tasks
        assert all(t.task_id in manager._tasks for t in results)

    def test_unbounded_concurrent_execution_investigation(self, tmp_path):
        """
        Stress Test 1B: Investigate max_concurrent_tasks enforcement.
        Checks whether max_concurrent_tasks actually limits the number of actively
        running tasks, or if all tasks are concurrently spawned up to max_total_workers.
        """
        max_concurrent = 2
        max_workers = 8
        manager = TaskManager(max_concurrent_tasks=max_concurrent, max_total_workers=max_workers)

        active_running_tasks = 0
        peak_running_tasks = 0
        counter_lock = threading.Lock()
        started_event = threading.Event()
        hold_event = threading.Event()

        def mock_get_items(req, cancel_event):
            nonlocal active_running_tasks, peak_running_tasks
            with counter_lock:
                active_running_tasks += 1
                if active_running_tasks > peak_running_tasks:
                    peak_running_tasks = active_running_tasks
                if active_running_tasks >= 4:
                    started_event.set()
            # Hold tasks so we can measure peak concurrent running tasks
            hold_event.wait(timeout=1.0)
            with counter_lock:
                active_running_tasks -= 1
            return [{"aweme_id": "test", "desc": "test", "awemeType": 0}]

        mock_service = MagicMock()
        mock_service.get_download_items.side_effect = mock_get_items

        with patch("src.douyin.download.Download.awemeDownload", return_value=True):
            for i in range(4):
                req = DownloadRequest(
                    url=f"https://www.douyin.com/video/74888934409320390{i}",
                    key_type="aweme",
                    key=f"74888934409320390{i}",
                    download_path=str(tmp_path),
                )
                manager.submit_task(req, douyin_service=mock_service)

            # Wait for tasks to enter mock_get_items
            started_event.wait(timeout=1.0)
            time.sleep(0.05)
            hold_event.set()

        print(f"\n[STRESS 1B] Configured max_concurrent_tasks={max_concurrent}, observed peak concurrent active tasks={peak_running_tasks}")
        # If peak_running_tasks > max_concurrent, max_concurrent_tasks is NOT enforced!
        assert peak_running_tasks <= max_concurrent, (
            f"VULNERABILITY: max_concurrent_tasks={max_concurrent} is UNENFORCED! "
            f"Observed {peak_running_tasks} concurrent tasks executing simultaneously."
        )

    # =========================================================================
    # 2. Immediate Cancellation Responsiveness & Thread Leak / Zombie Detection
    # =========================================================================

    def test_immediate_cancellation_during_chunk_stream(self, tmp_path):
        """
        Stress Test 2A: Cancel while download is actively streaming chunks.
        Verifies:
        - Cancellation is immediate (does not wait for all chunks)
        - Thread terminates cleanly without leaking
        - Final state is CANCELLED
        """
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
            download_path=str(tmp_path),
        )

        chunk_received_event = threading.Event()
        stream_thread_id = None
        thread_id_lock = threading.Lock()

        def slow_streaming_download(awemeDict, savePath, cancel_event=None, progress_callback=None):
            nonlocal stream_thread_id
            with thread_id_lock:
                stream_thread_id = threading.get_ident()

            for chunk_idx in range(100):
                if cancel_event and cancel_event.is_set():
                    return False
                if progress_callback:
                    progress_callback({
                        "event": "chunk",
                        "worker_id": 1,
                        "filename": "test.mp4",
                        "chunk_bytes": 1024,
                        "downloaded_bytes": (chunk_idx + 1) * 1024,
                        "total_bytes": 102400,
                    })
                chunk_received_event.set()
                # Simulate small chunk delay
                if cancel_event:
                    if cancel_event.wait(0.02):
                        return False
                else:
                    time.sleep(0.02)
            return True

        mock_service = MagicMock()
        mock_service.get_download_items.return_value = [{"aweme_id": "test", "desc": "test", "awemeType": 0}]

        with patch("src.douyin.download.Download.awemeDownload", side_effect=slow_streaming_download):
            resp = manager.submit_task(req, douyin_service=mock_service)
            # Wait for download to start streaming chunks
            assert chunk_received_event.wait(timeout=2.0), "Download never started streaming chunks!"

            cancel_start = time.monotonic()
            success = manager.cancel_task(resp.task_id)
            cancel_duration = time.monotonic() - cancel_start

            assert success is True
            print(f"\n[STRESS 2A] Cancellation call returned in {cancel_duration:.4f}s")

            # Wait up to 1.5s for worker thread to finish
            deadline = time.monotonic() + 1.5
            final_detail = None
            while time.monotonic() < deadline:
                final_detail = manager.get_task(resp.task_id)
                if final_detail.status == TaskStatus.CANCELLED and final_detail.active_threads == 0:
                    break
                time.sleep(0.02)

            assert final_detail.status == TaskStatus.CANCELLED
            assert final_detail.active_threads == 0
            print(f"[STRESS 2A] Task cleanly terminated in CANCELLED state")

    def test_cancel_on_paused_task_deadlock_vulnerability(self, tmp_path):
        """
        Stress Test 2B / VULNERABILITY AUDIT:
        When a task is PAUSED, the worker thread is blocked on `record.pause_event.wait()`.
        If the user cancels the paused task via `cancel_task(task_id)`:
        Does `cancel_task` wake up the worker thread, or does it leave the worker thread
        permanently blocked on `pause_event.wait()` (ZOMBIE THREAD / WORKER LEAK)?
        """
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
            download_path=str(tmp_path),
        )

        in_pause_wait_event = threading.Event()
        worker_finished_event = threading.Event()

        def pausing_download(awemeDict, savePath, cancel_event=None, progress_callback=None):
            # Emit first chunk which will trigger progress hook
            if progress_callback:
                progress_callback({
                    "event": "chunk",
                    "worker_id": 1,
                    "filename": "test.mp4",
                    "chunk_bytes": 1024,
                    "downloaded_bytes": 1024,
                    "total_bytes": 10240,
                })
            # Worker finished download if it reaches here
            worker_finished_event.set()
            return True

        mock_service = MagicMock()
        mock_service.get_download_items.return_value = [{"aweme_id": "test", "desc": "test", "awemeType": 0}]

        with patch("src.douyin.download.Download.awemeDownload", side_effect=pausing_download):
            resp = manager.submit_task(req, douyin_service=mock_service)
            record = manager._tasks[resp.task_id]

            # Wait until status is DOWNLOADING
            for _ in range(50):
                if record.status == TaskStatus.DOWNLOADING:
                    break
                time.sleep(0.01)

            # Pause task
            paused = manager.pause_task(resp.task_id)
            assert paused is True
            assert record.status == TaskStatus.PAUSED
            assert not record.pause_event.is_set(), "pause_event should be cleared"

            # Now, simulate worker thread calling progress hook while paused:
            # We run hook in a separate thread simulating the worker thread encountering pause_event.wait()
            hook = manager.create_progress_hook(record)
            hook_thread_blocked = threading.Event()

            def run_hook_worker():
                hook_thread_blocked.set()
                hook({
                    "event": "chunk",
                    "worker_id": 1,
                    "filename": "test.mp4",
                    "chunk_bytes": 1024,
                    "downloaded_bytes": 2048,
                    "total_bytes": 10240,
                })

            hook_thread = threading.Thread(target=run_hook_worker, daemon=True)
            hook_thread.start()
            hook_thread_blocked.wait(timeout=1.0)
            time.sleep(0.1)  # Ensure it has entered pause_event.wait()

            assert hook_thread.is_alive(), "Worker thread should be blocked waiting for pause_event"

            # Now CANCEL the paused task!
            print("\n[STRESS 2B] Cancelling a paused task...")
            cancel_success = manager.cancel_task(resp.task_id)
            assert cancel_success is True

            # Check if the blocked worker thread unblocks within 0.5 seconds:
            hook_thread.join(timeout=0.5)
            is_zombie = hook_thread.is_alive()
            print(f"[STRESS 2B] Worker thread is still alive/blocked after cancel: {is_zombie}")

            if is_zombie:
                print("CRITICAL FINDING: cancel_task does NOT wake up worker threads blocked on pause_event.wait()!")
                # Unblock the thread so test cleanup does not hang
                record.pause_event.set()
                hook_thread.join(timeout=1.0)

            # Assert whether the worker thread leaked
            assert not is_zombie, "ZOMBIE THREAD DETECTED: cancel_task failed to unblock worker waiting on pause_event!"

    # =========================================================================
    # 3. High-Frequency Chunk Emission, Throttling Suppression & SSE Queue Bounds
    # =========================================================================

    def test_high_frequency_chunk_emission_throttle_suppression(self):
        """
        Stress Test 3A: Rapid burst of 2,000 chunk events in rapid succession.
        Verifies:
        - 250ms throttle prevents event flooding
        - Suppresses > 95% of chunk events
        - Memory and lock contention do not bottleneck throughput
        """
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        record = TaskRecord("test_throttle_task", req)
        manager._tasks[record.task_id] = record

        # Create an asyncio event loop to capture broadcasts
        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)
        q = manager.subscribe(record.task_id)

        hook = manager.create_progress_hook(record)

        total_chunks = 2000
        start_time = time.monotonic()
        for i in range(total_chunks):
            hook({
                "event": "chunk",
                "worker_id": 1,
                "filename": "chunk_stress.mp4",
                "chunk_bytes": 1024,
                "downloaded_bytes": (i + 1) * 1024,
                "total_bytes": total_chunks * 1024,
            })
        duration = time.monotonic() - start_time

        # Process any pending callbacks in event loop
        loop.stop()
        loop.run_forever()

        events_received = q.qsize()
        suppression_pct = ((total_chunks - events_received) / total_chunks) * 100.0

        print(f"\n[STRESS 3A] Emitted {total_chunks} chunks in {duration:.4f}s")
        print(f"[STRESS 3A] Received events in SSE queue: {events_received}")
        print(f"[STRESS 3A] Chunk suppression rate: {suppression_pct:.2f}%")

        assert events_received < 50, f"Throttling failed: received {events_received} events (expected < 50)"
        assert suppression_pct >= 95.0, f"Expected >= 95% suppression, got {suppression_pct:.2f}%"
        loop.close()

    def test_sse_queue_overflow_and_slow_consumer(self):
        """
        Stress Test 3B: Slow consumer SSE queue overflow protection.
        Queue maxsize is 200. Push 300 forced events.
        Verifies:
        - Queue never raises QueueFull
        - Discards oldest events safely
        - Most recent event is retained at head
        """
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        record = TaskRecord("test_overflow_task", req)

        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)
        q = manager.subscribe(record.task_id)
        assert q.maxsize == 200

        # Push 300 forced events through broadcast
        for i in range(300):
            evt = DownloadProgressEvent(
                task_id=record.task_id,
                status=TaskStatus.DOWNLOADING,
                progress_pct=float(i),
                speed_bps=100.0,
                downloaded_bytes=i * 1000,
                total_bytes=300000,
                event_type="test",
                timestamp=datetime.now(timezone.utc),
            )
            manager._broadcast_event(evt, task_id=record.task_id, force=True)

        # Run loop to process all scheduled call_soon callbacks
        loop.stop()
        loop.run_forever()

        print(f"\n[STRESS 3B] Final queue size after 300 pushed events: {q.qsize()} (maxsize={q.maxsize})")
        assert q.qsize() == 200, f"Expected queue to be capped at 200, got {q.qsize()}"

        # Get latest event in queue to verify newest items are present
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        last_evt = items[-1]
        assert last_evt.progress_pct == 299.0, f"Latest event was dropped! Last progress_pct={last_evt.progress_pct}"
        loop.close()

    # =========================================================================
    # 4. Pause and Resume State Transitions & Race Conditions
    # =========================================================================

    def test_rapid_pause_resume_oscillations(self):
        """
        Stress Test 4A: Rapid pause/resume cycles (50 cycles) under multithreaded contention.
        Verifies:
        - No deadlocks between pause_task and resume_task
        - State accurately tracks PAUSED vs DOWNLOADING
        - pause_event is consistently synchronized with TaskStatus
        """
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        record = TaskRecord("test_oscillation_task", req)
        record.status = TaskStatus.DOWNLOADING
        manager._tasks[record.task_id] = record

        cycles = 50
        start = time.monotonic()
        for i in range(cycles):
            p = manager.pause_task(record.task_id)
            assert p is True
            assert record.status == TaskStatus.PAUSED
            assert not record.pause_event.is_set()

            r = manager.resume_task(record.task_id)
            assert r is True
            assert record.status == TaskStatus.DOWNLOADING
            assert record.pause_event.is_set()

        duration = time.monotonic() - start
        print(f"\n[STRESS 4A] Completed {cycles} pause/resume cycles in {duration:.4f}s")

    def test_exception_during_cancellation_masks_cancelled_state(self, tmp_path):
        """
        Stress Test 5: Verify if exception during cancellation erroneously marks task as FAILED.
        When a task is cancelled, network sockets or file operations often raise exceptions
        (e.g. ConnectionResetError, ChunkedEncodingError, or RequestAborted).
        If an exception is raised while cancel_event is set, does the status remain CANCELLED,
        or does it get overwritten with FAILED?
        """
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
            download_path=str(tmp_path),
        )

        worker_reached_event = threading.Event()
        worker_done_event = threading.Event()

        def download_raising_on_cancel(awemeDict, savePath, cancel_event=None, progress_callback=None):
            worker_reached_event.set()
            if cancel_event:
                cancel_event.wait(timeout=1.0)
            worker_done_event.set()
            # Raise exception simulating socket reset / aborted connection on cancel
            raise ConnectionResetError("Connection aborted by peer during cancellation")

        mock_service = MagicMock()
        mock_service.get_download_items.return_value = [{"aweme_id": "test", "desc": "test", "awemeType": 0}]

        with patch("src.douyin.download.Download.awemeDownload", side_effect=download_raising_on_cancel):
            resp = manager.submit_task(req, douyin_service=mock_service)
            worker_reached_event.wait(timeout=1.0)
            # Cancel task
            manager.cancel_task(resp.task_id)
            worker_done_event.wait(timeout=1.0)

            # Wait for pipeline exception handler to finish
            deadline = time.monotonic() + 1.0
            detail = manager.get_task(resp.task_id)
            while time.monotonic() < deadline and detail.active_threads > 0:
                detail = manager.get_task(resp.task_id)

            print(f"\n[STRESS 5] Task status after cancel followed by ConnectionResetError: {detail.status}")
            assert detail.status == TaskStatus.CANCELLED, (
                f"VULNERABILITY: Exception during cancellation overrode CANCELLED status to {detail.status}!"
            )

    def test_subscriber_and_task_record_memory_retention(self):
        """
        Stress Test 6: Audit memory cleanup for completed tasks and SSE subscriber queues.
        Verifies:
        - Whether TaskManager._subscribers retains subscriber sets for finished tasks
        - Whether TaskManager._tasks grows without bound
        """
        manager = TaskManager(max_concurrent_tasks=2, max_total_workers=4)
        req = DownloadRequest(
            url="https://www.douyin.com/video/7488893440932039970",
            key_type="aweme",
            key="7488893440932039970",
        )
        record = TaskRecord("test_memory_leak_task", req)
        manager._tasks[record.task_id] = record

        # Subscribe to task
        q = manager.subscribe(record.task_id)
        assert record.task_id in manager._subscribers

        # Finish task
        manager._finish_task(record, TaskStatus.COMPLETED)

        # Check if task_id still in _subscribers
        retained = record.task_id in manager._subscribers
        print(f"\n[STRESS 6] Finished task retained in _subscribers: {retained}")
        assert not retained, (
            "VULNERABILITY: TaskManager._subscribers leaks dictionary keys and sets for completed tasks!"
        )

    def test_quadratic_thread_explosion_in_user_download(self, tmp_path):
        """
        Stress Test 7: Verify thread concurrency bounds during userDownload.
        When userDownload runs with thread=6, does it bound total workers to 6,
        or does it nest ThreadPoolExecutor inside ThreadPoolExecutor spawning 30+ threads?
        """
        active_threads = set()
        thread_lock = threading.Lock()

        def mock_download_single(media_info):
            with thread_lock:
                active_threads.add(threading.get_ident())
            return True

        configured_threads = 6
        dl = Download(thread=configured_threads, music=True, cover=True, avatar=True, resjson=False)

        sample_awemes = [
            {
                "aweme_id": f"vid_{i}",
                "desc": f"video {i}",
                "awemeType": 0,
                "create_time": 1728000000 + i,
                "statistics": {"digg_count": 100},
                "video": {"play_addr": {"url_list": ["http://fake/v.mp4"]}},
                "music": {"title": "song", "play_url": {"url_list": ["http://fake/m.mp3"]}},
                "cover": {"url_list": ["http://fake/c.jpg"]},
                "author": {"avatar": {"url_list": ["http://fake/a.jpg"]}},
            }
            for i in range(10)
        ]

        with patch.object(dl, "_download_single_media", side_effect=mock_download_single):
            with patch.object(Path, "mkdir"):
                dl.userDownload(sample_awemes, savePath=tmp_path)

        spawned_threads = len(active_threads)
        print(f"\n[STRESS 7] Configured thread={configured_threads}, total worker threads spawned={spawned_threads}")
        assert spawned_threads <= configured_threads, (
            f"VULNERABILITY: Nested ThreadPoolExecutor caused quadratic thread explosion! "
            f"Expected <= {configured_threads} worker threads, but {spawned_threads} threads were spawned."
        )


