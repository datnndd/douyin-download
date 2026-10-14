// frontend/src/types/api.ts

export type TaskStatus =
  | 'PENDING'
  | 'PARSING'
  | 'RUNNING'
  | 'DOWNLOADING'
  | 'PAUSED'
  | 'CANCELLED'
  | 'COMPLETED'
  | 'FAILED';

export type KeyType = 'aweme' | 'user' | 'mix' | 'music' | 'live';
export type ContentType = 'video' | 'image' | 'user' | 'mix' | 'music' | 'live';

export interface AssetTypeToggles {
  video: boolean;
  music: boolean;
  cover: boolean;
  avatar: boolean;
  json: boolean;
}

export interface FilterOptions {
  sort_by: string;
  reverse: boolean;
  limit: number;
}

export interface StatisticsModel {
  digg_count: number;
  comment_count: number;
  share_count: number;
  play_count: number;
  collect_count: number;
  admire_count: number;
  follower_count?: number;
  total_favorited?: number;
  following_count?: number;
}

export interface AuthorPreview {
  nickname: string;
  avatar_thumb: string;
  sec_uid: string;
  avatar?: string;
  short_id?: string;
  unique_id?: string;
  signature?: string;
  follower_count?: number;
  total_favorited?: number;
  following_count?: number;
}

export interface PreviewMetadata {
  title: string;
  desc: string;
  author?: AuthorPreview;
  cover_url: string;
  statistics: StatisticsModel;
  duration?: number;
  work_count?: number;
  images: string[];
  extra: Record<string, any>;
}

export interface ParseRequest {
  url: string;
  cookie?: string;
}

export interface ParseResponse {
  success: boolean;
  url: string;
  canonical_url?: string;
  key_type: string;
  key: string;
  content_type: string;
  preview?: PreviewMetadata;
  error?: string;
}

export interface DownloadRequest {
  url: string;
  key_type?: string;
  key?: string;
  modes?: string[];
  asset_types?: AssetTypeToggles;
  thread_count?: number;
  filter?: FilterOptions;
  folderstyle?: boolean;
  download_path?: string;
  filename_template?: string;
  start_time?: string;
  end_time?: string;
  number?: Record<string, number>;
  increase?: Record<string, boolean>;
  database?: boolean;
  cookie?: string;
  aweme_ids?: string[];
}

export interface TaskResponse {
  task_id: string;
  status: TaskStatus;
  message: string;
  created_at: string;
}

export interface ThreadStatus {
  thread_id: number;
  status: string;
  current_file: string;
  pct: number;
  speed_bps: number;
}

export interface TaskDetailResponse {
  task_id: string;
  status: TaskStatus;
  progress_pct: number;
  downloaded_bytes: number;
  total_bytes: number;
  speed_bps: number;
  current_item: string;
  completed_items: number;
  total_items: number;
  active_threads: number;
  threads: ThreadStatus[];
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface DownloadProgressEvent {
  task_id: string;
  status: TaskStatus;
  progress_pct: number;
  speed_bps: number;
  downloaded_bytes: number;
  total_bytes: number;
  item_index: number;
  item_total: number;
  item_title: string;
  active_threads: number;
  threads: ThreadStatus[];
  event_type: string;
  timestamp: string;
}

export interface SettingsModel {
  path: string;
  music: boolean;
  cover: boolean;
  avatar: boolean;
  json: boolean;
  folderstyle: boolean;
  thread: number;
  filename_template?: string;
  cookies: Record<string, string>;
  raw_cookie?: string;
  start_time: string;
  end_time: string;
  database: boolean;
  mode: string[];
  number: Record<string, number>;
  increase: Record<string, boolean>;
  filter: FilterOptions;
  auto_track_downloads?: boolean;
  tracker_interval_hours?: number;
}

export interface MediaItem {
  id: string;
  filename: string;
  relative_path: string;
  media_type: 'video' | 'audio' | 'image' | 'json' | string;
  file_size: number;
  created_at: string;
  preview_url: string;
  download_url: string;
}

export interface MediaListResponse {
  items: MediaItem[];
  total: number;
}

export interface OpenFolderRequest {
  path?: string;
}

export interface OpenFolderResponse {
  success: boolean;
  opened_path: string;
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  disk_space: Record<string, any>;
  active_tasks: number;
}

export interface TrackedVideoItem {
  aweme_id: string;
  sec_uid: string;
  create_time?: number;
  title?: string;
  status: string;
  downloaded_at?: string;
}

export interface TrackedCreator {
  sec_uid: string;
  unique_id?: string;
  nickname?: string;
  avatar_thumb?: string;
  last_aweme_id?: string;
  last_aweme_time?: number;
  pending_new_count: number;
  last_checked_at?: string;
  last_downloaded_at?: string;
  created_at?: string;
  pending_videos?: TrackedVideoItem[];
}

export interface TrackCreatorRequest {
  url?: string;
  sec_uid?: string;
  nickname?: string;
  avatar_thumb?: string;
  unique_id?: string;
}

export interface TrackerStats {
  total_tracked_creators: number;
  total_pending_videos: number;
}

export interface CheckAllResponse {
  total_checked: number;
  new_videos_detected: number;
  creators_with_new: number;
}

