"""
src/web/services/task_manager.py
Centralized TaskManager service managing concurrent download tasks,
lifecycle state machine, bounded ThreadPoolExecutor, thread states visualizer,
cancellation tokens, and thread-safe SSE telemetry distribution.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

# In development/exploration, import schemas from proposed_schemas or src.web.core.schemas
try:
    from src.web.core.schemas import (
        DownloadProgressEvent,
        DownloadRequest,
        TaskDetailResponse,
        TaskResponse,
        TaskStatus,
        ThreadStatus,
    )
except ImportError:
    # Fallback to local proposed_schemas in M1 explorer directory for standalone verification
    import sys
    from pathlib import Path
    _m1_1_path = Path(__file__).resolve().parent.parent / "teamwork_preview_explorer_m1_1"
    if str(_m1_1_path) not in sys.path:
        sys.path.insert(0, str(_m1_1_path))
    from proposed_schemas import (
        DownloadProgressEvent,
        DownloadRequest,
        TaskDetailResponse,
        TaskResponse,
        TaskStatus,
        ThreadStatus,
    )

logger = logging.getLogger("Douyin.TaskManager")


class TaskRecord:
    """Internal state tracking entity for a single download job."""

    def __init__(self, task_id: str, request: DownloadRequest):
        self.task_id: str = task_id
        self.request: DownloadRequest = request
        self.status: TaskStatus = TaskStatus.PENDING
        self.progress_pct: float = 0.0
        self.downloaded_bytes: int = 0
        self.total_bytes: int = 0
        self.speed_bps: float = 0.0
        self.current_item: str = request.key or ""
        self.completed_items: int = 0
        self.total_items: int = 1
        self.active_threads: int = 0
        self.error: Optional[str] = None
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

        # Concurrency & cancellation controls
        self.cancel_event: threading.Event = threading.Event()
        self.pause_event: threading.Event = threading.Event()
        self.pause_event.set()  # set means NOT paused (running)

        # Worker thread visualizer slots (1-indexed matching thread_count)
        thread_count = max(1, min(request.thread_count, 32))
        self.threads: List[ThreadStatus] = [
            ThreadStatus(thread_id=i + 1, status="IDLE", current_file="", pct=0.0, speed_bps=0.0)
            for i in range(thread_count)
        ]

        # Internal metric calculation states
        self._lock: threading.Lock = threading.Lock()
        self._last_speed_calc_time: float = time.monotonic()
        self._last_speed_bytes: int = 0
        self._last_telemetry_emit_time: float = 0.0
        self._file_bytes_map: Dict[str, int] = {}  # filepath -> downloaded bytes

    def to_detail_response(self) -> TaskDetailResponse:
        """Create a thread-safe snapshot model for GET /api/tasks/{task_id}."""
        with self._lock:
            return TaskDetailResponse(
                task_id=self.task_id,
                status=self.status,
                progress_pct=round(self.progress_pct, 2),
                downloaded_bytes=self.downloaded_bytes,
                total_bytes=self.total_bytes,
                speed_bps=round(self.speed_bps, 2),
                current_item=self.current_item,
                completed_items=self.completed_items,
                total_items=self.total_items,
                active_threads=self.active_threads,
                threads=[t.model_copy() for t in self.threads],
                error=self.error,
                created_at=self.created_at,
                updated_at=self.updated_at,
            )

    def to_progress_event(self) -> DownloadProgressEvent:
        """Create a thread-safe telemetry event for SSE streaming."""
        with self._lock:
            return DownloadProgressEvent(
                task_id=self.task_id,
                status=self.status,
                progress_pct=round(self.progress_pct, 2),
                speed_bps=round(self.speed_bps, 2),
                downloaded_bytes=self.downloaded_bytes,
                total_bytes=self.total_bytes,
                item_index=self.completed_items,
                item_total=self.total_items,
                item_title=self.current_item,
                active_threads=self.active_threads,
                threads=[t.model_copy() for t in self.threads],
                event_type="task_progress",
                timestamp=datetime.now(timezone.utc),
            )

    def update_speed(self, now: float) -> None:
        """Smoothly recalculate instant and smoothed throughput (speed_bps)."""
        dt = now - self._last_speed_calc_time
        if dt >= 0.4:  # recalculate every ~400ms
            delta_bytes = self.downloaded_bytes - self._last_speed_bytes
            instant_speed = max(0.0, delta_bytes / dt)
            # EMA smoothing factor 0.35
            if self.speed_bps == 0.0:
                self.speed_bps = instant_speed
            else:
                self.speed_bps = 0.35 * instant_speed + 0.65 * self.speed_bps

            self._last_speed_calc_time = now
            self._last_speed_bytes = self.downloaded_bytes


class TaskManager:
    """
    Centralized singleton orchestrating background downloads.
    Features:
    - Bounded ThreadPoolExecutor preventing unconstrained thread spawning.
    - Lifecycle state machine: PENDING -> PARSING -> DOWNLOADING -> COMPLETED / FAILED / CANCELLED.
    - Thread-safe asyncio.Queue telemetry fan-out for SSE streams.
    - Worker thread visualizer tracking file, slot id, and percentage.
    - Throttled emission (~250ms) protecting event loops and clients.
    """

    _instance: Optional[TaskManager] = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __init__(self, max_concurrent_tasks: int = 4, max_total_workers: int = 16):
        if getattr(self, "_initialized", False):
            return

        self.max_concurrent_tasks: int = max_concurrent_tasks
        self.max_total_workers: int = max_total_workers

        # Bounded executor pool for all background tasks
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=max_total_workers,
            thread_name_prefix="TaskManagerWorker"
        )

        self._tasks: Dict[str, TaskRecord] = {}
        self._task_lock: threading.Lock = threading.Lock()

        # Telemetry SSE subscriber queues: task_id -> Set[asyncio.Queue]
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._global_subscribers: Set[asyncio.Queue] = set()
        self._sub_lock: threading.Lock = threading.Lock()

        # Event loop reference for thread-safe event scheduling
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._throttle_seconds: float = 0.250  # 250ms throttle limit

        self._initialized: bool = True
        logger.info(f"TaskManager initialized: max_workers={max_total_workers}, max_tasks={max_concurrent_tasks}")

    @classmethod
    def get_instance(cls, max_concurrent_tasks: int = 4, max_total_workers: int = 16) -> TaskManager:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls(max_concurrent_tasks, max_total_workers)
        return cls._instance

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind FastAPI asyncio event loop for thread-safe event queue dispatch."""
        self._loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Get bound event loop or active loop."""
        if self._loop and not self._loop.is_closed():
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    # ==========================================================================
    # Task Lifecycle Management
    # ==========================================================================

    def submit_task(self, request: DownloadRequest, douyin_service: Optional[Any] = None) -> TaskResponse:
        """
        Accept and enqueue a new download task.
        Transitions state to PENDING and submits execution to bounded ThreadPoolExecutor.
        """
        task_id = str(uuid.uuid4())
        record = TaskRecord(task_id=task_id, request=request)

        with self._task_lock:
            self._tasks[task_id] = record

        logger.info(f"Submitted task {task_id}: type={request.key_type}, key={request.key}")

        # Dispatch task to background executor
        self._executor.submit(self._run_task_pipeline, record, douyin_service)

        return TaskResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            message="Download task queued successfully",
            created_at=record.created_at,
        )

    def get_task(self, task_id: str) -> Optional[TaskDetailResponse]:
        """Fetch current status and metrics snapshot for a specific task."""
        with self._task_lock:
            record = self._tasks.get(task_id)
        if not record:
            return None
        return record.to_detail_response()

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TaskDetailResponse]:
        """List all tasks, optionally filtered by status, sorted newest first."""
        with self._task_lock:
            records = list(self._tasks.values())

        if status:
            records = [r for r in records if r.status == status]

        # Sort by creation time descending
        records.sort(key=lambda r: r.created_at, reverse=True)
        return [r.to_detail_response() for r in records]

    def cancel_task(self, task_id: str) -> bool:
        """
        Signal cancellation to a task via its threading.Event token.
        Transitions state to CANCELLED and broadcasts event.
        """
        with self._task_lock:
            record = self._tasks.get(task_id)

        if not record:
            logger.warning(f"Cancel requested for unknown task {task_id}")
            return False

        with record._lock:
            if record.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                logger.info(f"Task {task_id} is already in terminal state {record.status}")
                return False

            record.cancel_event.set()
            record.status = TaskStatus.CANCELLED
            record.updated_at = datetime.now(timezone.utc)

            # Mark all worker slots as IDLE/CANCELLED
            for slot in record.threads:
                if slot.status == "DOWNLOADING":
                    slot.status = "CANCELLED"
            record.active_threads = 0

        logger.info(f"Task {task_id} cancelled via token")
        self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)
        return True

    def pause_task(self, task_id: str) -> bool:
        """Pause a downloading task."""
        with self._task_lock:
            record = self._tasks.get(task_id)
        if not record:
            return False

        with record._lock:
            if record.status != TaskStatus.DOWNLOADING:
                return False
            record.pause_event.clear()  # clear signals pause
            record.status = TaskStatus.PAUSED
            record.updated_at = datetime.now(timezone.utc)

        self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)
        return True

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        with self._task_lock:
            record = self._tasks.get(task_id)
        if not record:
            return False

        with record._lock:
            if record.status != TaskStatus.PAUSED:
                return False
            record.pause_event.set()  # set signals resume
            record.status = TaskStatus.DOWNLOADING
            record.updated_at = datetime.now(timezone.utc)

        self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)
        return True

    # ==========================================================================
    # Real-Time SSE Telemetry & Subscriber Management
    # ==========================================================================

    def subscribe(self, task_id: Optional[str] = None) -> asyncio.Queue:
        """
        Register a new asyncio.Queue for SSE telemetry.
        If task_id is provided, subscribes to that task only; otherwise to global feed.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._sub_lock:
            if task_id:
                if task_id not in self._subscribers:
                    self._subscribers[task_id] = set()
                self._subscribers[task_id].add(queue)
            else:
                self._global_subscribers.add(queue)

        logger.debug(f"New SSE subscription added (task_id={task_id})")
        return queue

    def unsubscribe(self, queue: asyncio.Queue, task_id: Optional[str] = None) -> None:
        """Unregister an SSE queue to prevent memory leaks upon client disconnect."""
        with self._sub_lock:
            if task_id and task_id in self._subscribers:
                self._subscribers[task_id].discard(queue)
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]
            else:
                self._global_subscribers.discard(queue)

        logger.debug(f"SSE subscription removed (task_id={task_id})")

    def _broadcast_event(self, event: DownloadProgressEvent, task_id: Optional[str] = None, force: bool = False) -> None:
        """
        Thread-safely dispatch progress event to subscribers via loop.call_soon_threadsafe.
        """
        loop = self.get_event_loop()
        if not loop or loop.is_closed():
            return

        with self._sub_lock:
            targets = set(self._global_subscribers)
            if task_id and task_id in self._subscribers:
                targets.update(self._subscribers[task_id])

        if not targets:
            return

        def _push(q: asyncio.Queue, evt: DownloadProgressEvent):
            try:
                if q.full():
                    try:
                        q.get_nowait()  # discard oldest to avoid lag
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(evt)
            except Exception as e:
                logger.debug(f"Failed to push SSE event: {e}")

        for queue in targets:
            loop.call_soon_threadsafe(_push, queue, event)

    # ==========================================================================
    # Progress Callback & Throttling (~250ms)
    # ==========================================================================

    def create_progress_hook(self, record: TaskRecord) -> Callable[[Dict[str, Any]], None]:
        """
        Factory creating a progress callback function compatible with Download engine.
        Accepts raw dict telemetry events from worker threads, aggregates them into
        TaskRecord, recalculates speeds, updates thread slots, and throttles SSE dispatch.
        """
        def _hook(payload: Dict[str, Any]) -> None:
            now = time.monotonic()
            event_kind = payload.get("event", "chunk")
            worker_id = payload.get("worker_id", 1)
            file_name = payload.get("filename", "")
            chunk_bytes = payload.get("chunk_bytes", 0)
            file_downloaded = payload.get("downloaded_bytes", 0)
            file_total = payload.get("total_bytes", 0)

            # Check pause state (block worker thread if paused)
            record.pause_event.wait()

            with record._lock:
                record.updated_at = datetime.now(timezone.utc)

                # 1. Update downloaded byte metrics
                if chunk_bytes > 0:
                    record.downloaded_bytes += chunk_bytes

                # 2. Update worker slot in visualizer
                slot_idx = max(0, min(worker_id - 1, len(record.threads) - 1))
                slot = record.threads[slot_idx]

                if event_kind == "file_start":
                    slot.status = "DOWNLOADING"
                    slot.current_file = file_name
                    slot.pct = 0.0
                elif event_kind == "chunk":
                    slot.status = "DOWNLOADING"
                    slot.current_file = file_name
                    if file_total > 0:
                        slot.pct = round((file_downloaded / file_total) * 100.0, 1)
                elif event_kind == "file_complete":
                    slot.status = "COMPLETED"
                    slot.pct = 100.0
                elif event_kind == "file_error":
                    slot.status = "FAILED"

                # 3. Active thread count
                record.active_threads = sum(1 for t in record.threads if t.status == "DOWNLOADING")

                # 4. Update smooth throughput
                record.update_speed(now)

                # 5. Calculate overall progress %
                if record.total_bytes > 0:
                    record.progress_pct = min(100.0, (record.downloaded_bytes / record.total_bytes) * 100.0)
                elif record.total_items > 0:
                    record.progress_pct = min(100.0, (record.completed_items / record.total_items) * 100.0)

                # 6. Throttle check (~250ms)
                should_emit = False
                if event_kind in ("file_complete", "item_complete", "status_change"):
                    should_emit = True
                elif now - record._last_telemetry_emit_time >= self._throttle_seconds:
                    should_emit = True
                    record._last_telemetry_emit_time = now

            if should_emit:
                self._broadcast_event(record.to_progress_event(), task_id=record.task_id)

        return _hook

    # ==========================================================================
    # Task Pipeline Execution (Worker Thread)
    # ==========================================================================

    def _run_task_pipeline(self, record: TaskRecord, douyin_service: Optional[Any]) -> None:
        """
        Background worker pipeline:
        1. Transitions to PARSING.
        2. Resolves URL / queries Douyin API for metadata and items.
        3. Checks cancellation token.
        4. Transitions to DOWNLOADING.
        5. Instantiates Download engine with progress callback & cancel token.
        6. Executes downloads.
        7. Transitions to COMPLETED / FAILED / CANCELLED.
        """
        task_id = record.task_id
        req = record.request
        logger.info(f"Starting execution for task {task_id}")

        try:
            # ----------------- Phase 1: PARSING -----------------
            parsing_status = getattr(TaskStatus, "PARSING", getattr(TaskStatus, "RUNNING", TaskStatus.DOWNLOADING))
            with record._lock:
                record.status = parsing_status
                record.updated_at = datetime.now(timezone.utc)
            self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)

            if record.cancel_event.is_set():
                self._finish_task(record, TaskStatus.CANCELLED)
                return

            # Resolve items through DouyinService (or internal resolver)
            items = self._resolve_download_items(req, douyin_service, record.cancel_event)

            if record.cancel_event.is_set():
                self._finish_task(record, TaskStatus.CANCELLED)
                return

            if not items:
                logger.warning(f"Task {task_id} resolved 0 items to download")
                self._finish_task(record, TaskStatus.COMPLETED)
                return

            with record._lock:
                record.total_items = len(items)
                record.current_item = items[0].get("desc", req.key or "item")[:30]
                record.status = TaskStatus.DOWNLOADING
                record.updated_at = datetime.now(timezone.utc)
            self._broadcast_event(record.to_progress_event(), task_id=task_id, force=True)

            # ----------------- Phase 2: DOWNLOADING -----------------
            progress_hook = self.create_progress_hook(record)

            # Import Download engine
            from src.douyin.download import Download

            downloader = Download(
                thread=min(req.thread_count, len(record.threads)),
                music=req.asset_types.music,
                cover=req.asset_types.cover,
                avatar=req.asset_types.avatar,
                resjson=req.asset_types.json,
                folderstyle=req.folderstyle,
                progress_callback=progress_hook,
                cancel_event=record.cancel_event,
            )

            destination = Path(req.download_path).resolve()
            destination.mkdir(parents=True, exist_ok=True)

            # Process items
            if req.key_type == "aweme" and len(items) == 1:
                aweme_dict = items[0]
                save_out = destination / "aweme"
                downloader.awemeDownload(
                    awemeDict=aweme_dict,
                    savePath=save_out,
                    cancel_event=record.cancel_event,
                    progress_callback=progress_hook,
                )
                with record._lock:
                    record.completed_items = 1
            else:
                # User / Mix / Multiple items
                downloader.userDownload(
                    awemeList=items,
                    savePath=destination,
                    cancel_event=record.cancel_event,
                    progress_callback=progress_hook,
                )
                with record._lock:
                    record.completed_items = len(items)

            # Check if cancelled during download
            if record.cancel_event.is_set():
                self._finish_task(record, TaskStatus.CANCELLED)
            else:
                self._finish_task(record, TaskStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Task {task_id} execution error: {e}", exc_info=True)
            with record._lock:
                record.error = str(e)
            self._finish_task(record, TaskStatus.FAILED)

    def _resolve_download_items(
        self, req: DownloadRequest, douyin_service: Optional[Any], cancel_event: threading.Event
    ) -> List[Dict[str, Any]]:
        """
        Resolve items to download using DouyinService or direct DouyinApi client.
        Supports single video, user profiles, mixes, and music.
        """
        if douyin_service and hasattr(douyin_service, "get_download_items"):
            return douyin_service.get_download_items(req, cancel_event)

        # Fallback to direct DouyinApi if douyin_service wrapper not supplied
        from src.douyin.douyinapi import DouyinApi

        api = DouyinApi()
        url = req.url
        key_type = req.key_type
        key = req.key

        if not key:
            share_url = api.getShareLink(url)
            key_type, key = api.getKey(share_url)

        if not key or cancel_event.is_set():
            return []

        if key_type == "aweme":
            aweme = api.getAwemeInfoApi(key)
            return [aweme] if aweme else []

        elif key_type == "user":
            all_items = []
            for mode in req.modes:
                if cancel_event.is_set():
                    break
                limit = req.number.get(mode, 0) if req.number else 0
                data = api.getUserInfoApi(
                    sec_uid=key,
                    mode=mode,
                    count=35,
                    number=limit,
                    start_time=req.start_time,
                    end_time=req.end_time,
                )
                if data:
                    all_items.extend(data)
            return all_items

        elif key_type == "mix":
            limit = req.number.get("mix", 0) if req.number else 0
            data = api.getMixInfoApi(
                mix_id=key,
                count=35,
                number=limit,
                start_time=req.start_time,
                end_time=req.end_time,
            )
            return data or []

        elif key_type == "music":
            limit = req.number.get("music", 0) if req.number else 0
            data = api.getMusicInfo(
                music_id=key,
                count=35,
                number=limit,
                start_time=req.start_time,
                end_time=req.end_time,
            )
            return data or []

        return []

    def _finish_task(self, record: TaskRecord, final_status: TaskStatus) -> None:
        """Mark task as finished, update final telemetry, and broadcast final event."""
        with record._lock:
            record.status = final_status
            record.updated_at = datetime.now(timezone.utc)
            record.speed_bps = 0.0
            record.active_threads = 0
            if final_status == TaskStatus.COMPLETED:
                record.progress_pct = 100.0
            for slot in record.threads:
                if slot.status == "DOWNLOADING":
                    slot.status = "COMPLETED" if final_status == TaskStatus.COMPLETED else "IDLE"

        logger.info(f"Task {record.task_id} completed with status {final_status}")
        self._broadcast_event(record.to_progress_event(), task_id=record.task_id, force=True)

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shutdown background executor."""
        logger.info("Shutting down TaskManager worker pool...")
        with self._task_lock:
            for task in self._tasks.values():
                task.cancel_event.set()
        self._executor.shutdown(wait=wait)
