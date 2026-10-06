# -*- coding: utf-8 -*-
"""
src/web/core/schemas.py
Pydantic v2 schemas for Douyin Web Downloader.
Defines models for parse requests/responses, preview metadata,
download task orchestration, telemetry events, settings, and media library.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
import warnings

warnings.filterwarnings(
    "ignore",
    message=r'.*shadows an attribute in parent "BaseModel".*',
    category=UserWarning,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Enums
# ==============================================================================


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    RUNNING = "RUNNING"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class KeyType(str, Enum):
    AWEME = "aweme"
    USER = "user"
    MIX = "mix"
    MUSIC = "music"
    LIVE = "live"


class ContentType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    USER = "user"
    MIX = "mix"
    MUSIC = "music"
    LIVE = "live"


# ==============================================================================
# Filter & Toggle Sub-models
# ==============================================================================


class AssetTypeToggles(BaseModel):
    """Selective asset toggles for downloads."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    video: bool = Field(default=True, description="Download main video file")
    music: bool = Field(default=True, description="Download background music audio")
    cover: bool = Field(default=True, description="Download video cover image")
    avatar: bool = Field(default=False, description="Download creator avatar")
    json: bool = Field(default=True, description="Save metadata result JSON file")


class FilterOptions(BaseModel):
    """Sorting and filtering criteria for user/mix works."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    sort_by: str = Field(
        default="create_time",
        description="Sort field: play_count, digg_count, comment_count, share_count, create_time",
    )
    reverse: bool = Field(
        default=True,
        description="True for descending (highest / newest first), False for ascending",
    )
    limit: int = Field(
        default=0,
        ge=0,
        description="Maximum items to download after sorting (0 = download all)",
    )


class StatisticsModel(BaseModel):
    """Aggregated engagement metrics."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    digg_count: int = Field(default=0, description="Likes count")
    comment_count: int = Field(default=0, description="Comments count")
    share_count: int = Field(default=0, description="Shares count")
    play_count: int = Field(default=0, description="Video view count")
    collect_count: int = Field(default=0, description="Favorites count")
    admire_count: int = Field(default=0, description="Admiration count")
    follower_count: Optional[int] = Field(default=0, description="Follower count")
    total_favorited: Optional[int] = Field(
        default=0, description="Total likes received"
    )
    following_count: Optional[int] = Field(default=0, description="Following count")

    @field_validator(
        "digg_count",
        "comment_count",
        "share_count",
        "play_count",
        "collect_count",
        "admire_count",
        "follower_count",
        "total_favorited",
        "following_count",
        mode="before",
    )
    @classmethod
    def coerce_numeric(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0


# Alias for backward-compatibility with Explorer 2 code
PreviewStatistics = StatisticsModel


# ==============================================================================
# Preview & Author Models
# ==============================================================================


class AuthorPreview(BaseModel):
    """Author summary for content preview card."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    nickname: str = Field(default="", description="Creator nickname")
    avatar_thumb: str = Field(default="", description="Creator thumbnail avatar URL")
    sec_uid: str = Field(default="", description="Douyin sec_user_id token")
    avatar: Optional[str] = Field(
        default=None, description="HD creator avatar URL if available"
    )
    short_id: Optional[str] = None
    unique_id: Optional[str] = None
    signature: Optional[str] = None
    follower_count: Optional[int] = 0
    total_favorited: Optional[int] = 0

    @field_validator("avatar_thumb", "avatar", mode="before")
    @classmethod
    def extract_avatar_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list", [])
            return url_list[0] if url_list else ""
        return str(v or "")

    @field_validator("follower_count", "total_favorited", mode="before")
    @classmethod
    def coerce_counts(cls, v: Any) -> int:
        if v is None or v == "":
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0


class PreviewMetadata(BaseModel):
    """Detailed preview payload for Step 1 preview card."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    title: str = Field(default="", description="Content title or caption snippet")
    desc: str = Field(default="", description="Full description text")
    author: Optional[AuthorPreview] = Field(default=None, description="Creator details")
    cover_url: str = Field(default="", description="Video / note cover thumbnail URL")
    statistics: StatisticsModel = Field(
        default_factory=StatisticsModel, description="Engagement counters"
    )
    duration: Optional[int] = Field(default=None, description="Video length in seconds")
    work_count: Optional[int] = Field(
        default=1, description="Estimated number of downloadable works"
    )
    images: List[str] = Field(
        default_factory=list, description="Image URLs if note/album"
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @field_validator("cover_url", mode="before")
    @classmethod
    def extract_cover_url(cls, v: Any) -> str:
        if isinstance(v, dict):
            url_list = v.get("url_list", [])
            return url_list[0] if url_list else ""
        return str(v or "")


# ==============================================================================
# Endpoint Request & Response Models
# ==============================================================================


class ParseRequest(BaseModel):
    """Request payload for POST /api/parse."""

    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., min_length=1, description="Raw Douyin share text or URL")
    cookie: Optional[str] = Field(
        default=None, description="Optional custom cookie string override"
    )


class ParseResponse(BaseModel):
    """Response payload for POST /api/parse."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    url: str = Field(..., description="Original requested URL")
    canonical_url: Optional[str] = Field(
        default=None, description="Resolved full Douyin URL"
    )
    key_type: str = Field(..., description="Entity type: aweme, user, mix, music, live")
    key: str = Field(..., description="Extracted entity ID or sec_uid")
    content_type: str = Field(
        default="video", description="Detected media content type"
    )
    preview: Optional[PreviewMetadata] = Field(
        default=None, description="Extracted card preview info"
    )
    error: Optional[str] = Field(
        default=None, description="Error explanation if failed"
    )


class DownloadRequest(BaseModel):
    """Request payload for POST /api/download."""

    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., description="Target Douyin URL")
    key_type: str = Field(default="aweme", description="aweme, user, mix, music, live")
    key: str = Field(default="", description="Target ID or sec_uid")
    modes: List[str] = Field(
        default_factory=lambda: ["post"],
        description="For user profiles: ['post'], ['like'], or ['post', 'like']",
    )
    asset_types: AssetTypeToggles = Field(
        default_factory=AssetTypeToggles,
        description="Selective toggles for video, audio, cover, avatar, json",
    )
    thread_count: int = Field(
        default=5, ge=1, le=32, description="Worker pool concurrency"
    )
    filter: FilterOptions = Field(
        default_factory=FilterOptions, description="Sorting and limit options"
    )
    folderstyle: bool = Field(
        default=True, description="True for subfolders, False for flat"
    )
    download_path: str = Field(
        default="./Downloaded/", description="Target destination folder"
    )
    start_time: str = Field(default="", description="Date filter start YYYY-MM-DD")
    end_time: str = Field(default="", description="Date filter end YYYY-MM-DD")
    number: Dict[str, int] = Field(
        default_factory=lambda: {
            "post": 0,
            "like": 0,
            "allmix": 0,
            "mix": 5,
            "music": 5,
        },
        description="Work limits per target mode",
    )
    increase: Dict[str, bool] = Field(
        default_factory=lambda: {
            "post": False,
            "like": False,
            "allmix": False,
            "mix": False,
            "music": False,
        },
        description="Incremental SQLite WAL deduplication toggles",
    )
    database: bool = Field(
        default=False, description="Enable SQLite deduplication cache"
    )
    cookie: Optional[str] = Field(
        default=None, description="Optional custom cookie string override"
    )


class TaskResponse(BaseModel):
    """Response payload for POST /api/download (202 Accepted)."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., description="Unique UUID identifier for the queued job")
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, description="Initial task status"
    )
    message: str = Field(
        default="Download task queued successfully", description="Status message"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Task creation timestamp",
    )


class ThreadStatus(BaseModel):
    """Telemetry representation of an individual worker thread."""

    model_config = ConfigDict(populate_by_name=True)

    thread_id: int = Field(..., description="Worker thread index 1..N")
    status: str = Field(
        default="IDLE",
        description="Worker state: IDLE, DOWNLOADING, COMPLETED, FAILED, CANCELLED",
    )
    current_file: str = Field(
        default="", description="Name of file currently being fetched"
    )
    pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Thread item download percentage"
    )
    speed_bps: float = Field(
        default=0.0, ge=0.0, description="Thread instant throughput in bytes/sec"
    )


class TaskDetailResponse(BaseModel):
    """Response payload for GET /api/tasks/{task_id}."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., description="Task unique identifier")
    status: TaskStatus = Field(..., description="Current status of the task")
    progress_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Overall completion percentage"
    )
    downloaded_bytes: int = Field(
        default=0, ge=0, description="Total bytes downloaded so far"
    )
    total_bytes: int = Field(
        default=0, ge=0, description="Estimated total bytes for current items"
    )
    speed_bps: float = Field(
        default=0.0, ge=0.0, description="Aggregate download speed in bytes/sec"
    )
    current_item: str = Field(
        default="", description="ID or title of item currently being processed"
    )
    completed_items: int = Field(default=0, ge=0, description="Count of finished items")
    total_items: int = Field(
        default=0, ge=0, description="Total count of scheduled items"
    )
    active_threads: int = Field(
        default=0, ge=0, description="Count of active downloading workers"
    )
    threads: List[ThreadStatus] = Field(
        default_factory=list, description="Worker pool telemetry"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if task failed"
    )
    created_at: datetime = Field(..., description="Timestamp when task was submitted")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last telemetry update",
    )


class DownloadProgressEvent(BaseModel):
    """Real-time Server-Sent Event or WebSocket progress message."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str
    status: TaskStatus = TaskStatus.DOWNLOADING
    progress_pct: float = 0.0
    speed_bps: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    item_index: int = 0
    item_total: int = 0
    item_title: str = ""
    active_threads: int = 0
    threads: List[ThreadStatus] = Field(default_factory=list)
    event_type: str = "task_progress"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ==============================================================================
# Settings Models
# ==============================================================================


class SettingsModel(BaseModel):
    """Configuration schema matching config.yaml."""

    model_config = ConfigDict(populate_by_name=True)

    path: str = Field(
        default="./Downloaded/", description="Default download root directory"
    )
    music: bool = Field(default=True, description="Download background audio")
    cover: bool = Field(default=True, description="Download cover images")
    avatar: bool = Field(default=False, description="Download creator avatars")
    json: bool = Field(default=True, description="Save result JSON metadata")
    folderstyle: bool = Field(default=True, description="Organize items in subfolders")
    thread: int = Field(
        default=5, ge=1, le=32, description="Default concurrency thread count"
    )
    cookies: Dict[str, str] = Field(
        default_factory=dict, description="Parsed cookie key-value dictionary"
    )
    raw_cookie: Optional[str] = Field(
        default=None, description="Raw semicolon-delimited cookie string"
    )
    start_time: str = Field(default="", description="Start date filter YYYY-MM-DD")
    end_time: str = Field(default="", description="End date filter YYYY-MM-DD")
    database: bool = Field(
        default=False, description="Enable SQLite database persistence"
    )
    mode: List[str] = Field(
        default_factory=lambda: ["post"], description="Default modes"
    )
    number: Dict[str, int] = Field(
        default_factory=lambda: {
            "post": 0,
            "like": 0,
            "allmix": 0,
            "mix": 5,
            "music": 5,
        }
    )
    increase: Dict[str, bool] = Field(
        default_factory=lambda: {
            "post": False,
            "like": False,
            "allmix": False,
            "mix": False,
            "music": False,
        }
    )
    filter: FilterOptions = Field(default_factory=FilterOptions)


# ==============================================================================
# Media Library & System Models
# ==============================================================================


class MediaItem(BaseModel):
    """Discovered media item in the storage directory."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique media file identifier")
    filename: str = Field(..., description="Disk filename")
    relative_path: str = Field(..., description="Relative path from download root")
    media_type: str = Field(..., description="video, audio, image, json")
    file_size: int = Field(default=0, description="Size in bytes")
    created_at: datetime = Field(..., description="File modification/creation time")
    preview_url: str = Field(
        ..., description="HTTP Range streaming URL for in-browser playback"
    )
    download_url: str = Field(..., description="Attachment download URL")


class MediaListResponse(BaseModel):
    """Response payload for GET /api/media."""

    model_config = ConfigDict(populate_by_name=True)

    items: List[MediaItem] = Field(default_factory=list)
    total: int = 0


class OpenFolderRequest(BaseModel):
    """Request payload for POST /api/open-folder."""

    model_config = ConfigDict(populate_by_name=True)

    path: Optional[str] = Field(
        default="", description="Relative subfolder or empty for root"
    )


class OpenFolderResponse(BaseModel):
    """Response payload for POST /api/open-folder."""

    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    opened_path: str = ""
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response payload for GET /api/health."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = "ok"
    version: str = "1.0.0"
    disk_space: Dict[str, Any] = Field(default_factory=dict)
    active_tasks: int = 0
