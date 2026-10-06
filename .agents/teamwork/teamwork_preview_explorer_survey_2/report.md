# Frontend Architecture & Design System Survey Report
**Project:** Douyin Web Downloader  
**Date:** 2026-10-06  
**Role:** Codebase Explorer (Frontend Architect & Design System Surveyor)  
**Target Platform:** React 19 + TypeScript + Vite 6 + Tailwind CSS v4 + FastAPI  
**Reference Design System:** `pyvideotrans` Warm Editorial Aesthetic (`#FAF8F5`, `#8D4B00`, `#F3ECE2`)

---

## 1. Executive Summary

This report delivers the comprehensive architectural blueprint for the web frontend of the Douyin Web Downloader application. It transforms the current CLI script workflow (`douyinCommand.py` and `src/douyin/`) into a desktop-grade web application running on React 19, TypeScript, and Vite.

The visual language directly imports the warm editorial aesthetic of `pyvideotrans` (`c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css`), eliminating generic dashboard defaults in favor of ivory surface backgrounds (`#FAF8F5`), rich terracotta/amber primary accents (`#8D4B00`), warm container surfaces (`#F3ECE2`), and dual typography with *Plus Jakarta Sans* and *JetBrains Mono*.

Key workflow innovations include:
1. **Two-Step Download Workflow**: Intelligent URL parsing and real-time content preview card (author avatar, nickname, video thumbnail, title, statistics, item counts) followed by fine-grained configuration and execution.
2. **Real-Time Progress Tracker**: Telemetry powered by Server-Sent Events (SSE) displaying global throughput (`MB/s`), total percentage, and an active worker thread pool visualizer tracking concurrent chunk downloads.
3. **Storage & Media Library**: In-browser media browsing with video/audio HTML5 playback, metadata drawer, and a native Windows File Explorer launcher (`os.startfile`).
4. **Settings & Cookie Manager**: Dual-format Douyin cookie configuration (visual token inputs and raw string), interactive cookie validation against Douyin endpoints, and lossless `config.yaml` synchronization.
5. **Unified FastAPI Production Mount**: Single-command execution (`python webui.py`) where FastAPI serves the compiled SPA static files and auto-opens the browser.

---

## 2. Design System & Token Extraction from Pyvideotrans

Analysis of `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css` and its screen components reveals an intentional, cohesive design token system:

### 2.1 CSS Theme Variables (Tailwind CSS v4 `@theme`)

```css
@import "tailwindcss";

@theme {
  /* Surfaces & Canvas */
  --color-surface: #FAF8F5;                 /* Warm ivory canvas background */
  --color-surface-container: #F3ECE2;       /* Warm neutral container */
  --color-surface-container-low: #FAF6F0;   /* Light card background */
  --color-surface-container-high: #EDE5DA;  /* Elevated panel / hover state */
  --color-surface-container-lowest: #FFFFFF;/* Pure white card backgrounds */

  /* Text & Foregrounds */
  --color-on-surface: #1F2328;              /* Charcoal primary text */
  --color-on-surface-variant: #595E68;      /* Muted slate secondary text */

  /* Outlines & Borders */
  --color-outline: #898174;                 /* Medium border contrast */
  --color-outline-variant: #E5DED4;         /* Subtle warm border (#E7E4DC / #E5DED4) */

  /* Primary Brand (Terracotta / Amber) */
  --color-primary: #8D4B00;                 /* Deep terracotta primary accent */
  --color-primary-hover: #743D00;           /* Dark terracotta hover */
  --color-primary-container: #B15F00;       /* Rich amber container */
  --color-primary-light: #FFDCC3;          /* Warm peach tint / badge fill */
  --color-on-primary: #FFFFFF;              /* Pure white text on primary */

  /* Semantic & Secondary */
  --color-secondary: #A13E28;               /* Warm rust / danger accent */
  --color-tertiary: #506053;                /* Muted sage / secondary accent */
  --color-success: #10B981;                 /* Emerald status indicator */
  --color-warning: #F59E0B;                 /* Amber pending status */
  --color-error: #E11D48;                   /* Rose error badge */

  /* Typography */
  --font-sans: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
```

### 2.2 Global Styling & Component Motifs

1. **Body & Scrollbars**:
   - `background-color: #FAF8F5; color: #1F2328; font-family: var(--font-sans);`
   - Custom sleek scrollbar: 5px width, rounded `#D5CFC5` thumb, `#B4ADA1` hover, transparent track.
2. **Card Structure**:
   - Background: `bg-white` with `border border-[#E7E4DC]` (or `border-stone-200/80`).
   - Radius: `rounded-xl` (12px) for form cards; `rounded-2xl` (16px) for modals and master containers.
   - Elevation: Subtle depth using `shadow-2xs` (`0 1px 2px rgba(0,0,0,0.03)`) and `shadow-xs`.
3. **Pill Badges & Tabs**:
   - Tab container: `bg-stone-100/80 rounded-lg border border-stone-200/80 p-0.5 text-[11px]`.
   - Active Tab: `bg-white text-[#8D4B00] font-bold shadow-2xs border border-amber-200/80`.
   - Inactive Tab: `text-stone-600 hover:text-stone-900 hover:bg-stone-200/50`.
4. **Header & Footer Dimensions**:
   - Top Header: Fixed height `h-[50px]`, `border-b border-[#E7E4DC]`, `bg-white`.
   - Bottom Status Footer: Fixed height `h-[52px]`, `border-t border-[#E7E4DC]`, `bg-white`.
   - Stepper / Subheader: Fixed height `h-9` (36px), `bg-[#FAF8F5] border-b border-[#E7E4DC]`.
5. **Interactive Pulse & Telemetry**:
   - Animated pulse: `@keyframes warm-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }`.
   - Status indicators: Emerald glowing dot (`bg-emerald-500 warm-pulse`) for backend health and idle worker states.

---

## 3. Technology Stack & Package Architecture

### 3.1 Dependencies Specification (`frontend/package.json`)

```json
{
  "name": "douyin-downloader-web",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.3",
    "lucide-react": "^1.16.0",
    "@tailwindcss/vite": "^4.0.9",
    "tailwindcss": "^4.0.9",
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.0.2",
    "@radix-ui/react-dialog": "^1.1.6",
    "@radix-ui/react-dropdown-menu": "^2.1.6",
    "@radix-ui/react-progress": "^1.1.2",
    "@radix-ui/react-slider": "^1.2.3",
    "@radix-ui/react-tabs": "^1.1.3",
    "@radix-ui/react-tooltip": "^1.1.8"
  },
  "devDependencies": {
    "@types/react": "^19.0.10",
    "@types/react-dom": "^19.0.4",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.3",
    "vite": "^6.2.0"
  }
}
```

### 3.2 Vite Configuration (`frontend/vite.config.ts`)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
});
```

---

## 4. Application Architecture & Component Hierarchy

### 4.1 Component Tree Diagram

```
<App>
 ├── <Header />
 │    ├── Branding & Logo (Terracotta Waves Icon + "Douyin Downloader")
 │    ├── Primary View Navigation Tabs ([Downloader], [Media Library], [Task History])
 │    ├── Global Active Task Telemetry Pill (Total Speed MB/s, Active Threads)
 │    └── Actions ([Open Settings Modal], [System Status Badge])
 │
 ├── <main className="flex-1 overflow-hidden">
 │    │
 │    ├── [View: Downloader]
 │    │    ├── <WorkflowStepper /> (Step 1: Link & Preview ➔ Step 2: Configure & Download)
 │    │    │
 │    │    ├── (If Step == 1) <Step1LinkPreview />
 │    │    │    ├── <UrlInputField /> (Paste button, URL validation, Quick Sample links)
 │    │    │    ├── <PreviewCardSkeleton /> (Loading shimmer state)
 │    │    │    └── <PreviewCard /> (Author info, Thumbnail, Stats, Work count, "Configure ➔")
 │    │    │
 │    │    ├── (If Step == 2) <Step2ConfigExecution />
 │    │    │    ├── <TargetModeSelector /> (For user profiles: Post, Like, AllMix)
 │    │    │    ├── <AssetTogglesCard /> (Video, Audio MP3, Cover, Avatar, JSON)
 │    │    │    ├── <FilterSortCard /> (Sort by digg/play count, Date range, Limit)
 │    │    │    ├── <ConcurrencyStorageCard /> (Worker threads slider 1-32, Folderstyle toggle)
 │    │    │    └── <ExecutionActionBar /> (Summary count, "Start Download" primary button)
 │    │    │
 │    │    └── <ActiveTaskTracker />
 │    │         ├── <OverallProgressBanner /> (Percentage, Downloaded/Total, ETA, Cancel)
 │    │         ├── <ActiveThreadsGrid /> (Worker 1..N: in-flight chunk, speed, asset type)
 │    │         └── <LiveActivityFeed /> (Real-time completed item chips)
 │    │
 │    ├── [View: MediaLibrary]
 │    │    ├── <MediaToolbar />
 │    │    │    ├── Search Input & Media Type Filter Chips (All, Videos, Audio, Images)
 │    │    │    ├── Sort Dropdown (Date, Size, Likes) & Grid/List View Toggle
 │    │    │    └── "Open in Explorer" Native Button
 │    │    ├── <MediaGrid /> or <MediaTable />
 │    │    │    └── <MediaItemCard /> (Poster thumbnail, Duration, Digg count, Actions)
 │    │    └── <MediaPreviewDrawer /> (HTML5 Video/Audio Player, Scrub Bar, Info Panel)
 │    │
 │    └── [View: TaskHistory]
 │         └── <TaskHistoryTable /> (Historical jobs, status, item counts, log view)
 │
 ├── <StatusFooter />
 │    ├── Left: System Heartbeat (FastAPI connection, Cookie readiness)
 │    ├── Center: Active task quick-summary
 │    └── Right: Active Thread Pool Monitor & Storage directory path
 │
 └── <SettingsModal />
      ├── Tabs: [Douyin Cookies], [Storage & Paths], [Network & Engine]
      ├── <CookieTab /> (Key-value fields, Raw cookie string, Test & Validate button)
      ├── <StorageTab /> (Download path, Folderstyle, Disk usage bar)
      └── <EngineTab /> (Default thread pool, User-agent, Proxy URL)
```

---

## 5. Two-Step Interaction Workflow Specification

### 5.1 Step 1: Link Input & Content Preview

The user inputs any Douyin URL (desktop link or mobile share link `https://v.douyin.com/...`).

#### 5.1.1 URL Parsing Flow
1. User pastes link into `<UrlInputField />`.
2. Frontend calls `POST /api/parse`:
   ```json
   { "url": "https://v.douyin.com/8muR-7iUO6E/" }
   ```
3. Backend invokes `DouyinApi.getKey(url)` and resolves link type:
   - `aweme`: Single video or image note
   - `user`: Creator profile
   - `mix`: Collection / Playlist
   - `music`: Original sound collection
   - `live`: Livestream room

#### 5.1.2 Preview Metadata Schema & Card Presentation
The returned payload populates the `<PreviewCard />`:

```typescript
export interface LinkPreviewData {
  keyType: 'aweme' | 'user' | 'mix' | 'music' | 'live';
  keyId: string;
  originalUrl: string;
  author: {
    nickname: string;
    avatarUrl: string;
    secUid?: string;
    signature?: string;
    followerCount?: number;
    totalFavorited?: number;
  };
  content: {
    title: string;
    coverUrl: string;
    awemeType?: number; // 0 = Video, 1 = Image Album
    createTime?: number;
    durationMs?: number;
    stats?: {
      playCount: number;
      diggCount: number;
      commentCount: number;
      shareCount: number;
    };
    estimatedItemsCount?: number; // Total works for profile/mix
  };
}
```

#### 5.1.3 Preview Visual Layout
- **Left Column**: Thumbnail/Poster with rounded corners (`rounded-xl`), aspect ratio container (16:9 or 9:16 portrait), duration tag overlay, and "Play Preview" hover button.
- **Right Column**:
  - Top: Author avatar badge (`rounded-full ring-2 ring-amber-500/20`), author nickname, and `keyType` badge (e.g. `Single Video`, `User Profile`, `Mix Album`).
  - Middle: Video description/title (`text-sm font-semibold text-stone-900 line-clamp-3`).
  - Stats Row: Digg count (`❤️ 2.4M`), Comment count (`💬 48.2K`), Share count (`🔄 12.1K`).
  - Bottom: Action strip featuring a secondary "Clear" button and a terracotta primary button:
    `<button className="bg-[#8D4B00] hover:bg-[#743D00] text-white px-5 py-2 rounded-lg font-bold text-xs flex items-center gap-2">Configure &amp; Download <ArrowRight className="w-4 h-4" /></button>`

---

### 5.2 Step 2: Configuration & Download Execution

Upon clicking "Configure & Download", the view smoothly transitions to Step 2, presenting clear, grouped configuration cards:

#### 5.2.1 Target Mode Selector (For User Profiles)
When `keyType === 'user'`, renders selectable pill buttons:
- **Posted Works (`post`)**: Download author's uploaded works.
- **Liked Works (`like`)**: Download author's public likes.
- **Collections (`mix`)**: Download all albums/mixes created by the author.

#### 5.2.2 Asset Toggles Card
Interactive toggle chips with icon, title, file extension, and checkbox:
- **Video (`.mp4`)**: Watermark-free original video (default: `true`).
- **Original Audio (`.mp3`)**: Extracted BGM / sound track (default: `false` or from `config.yaml`).
- **Cover Image (`.jpeg`)**: Video poster thumbnail (default: `false`).
- **Author Avatar (`.jpeg`)**: Profile avatar image (default: `false`).
- **Metadata JSON (`.json`)**: Raw aweme attributes and statistics (default: `false`).

#### 5.2.3 Download Filters & Limits
- **Max Works to Download (`limit`)**: Numeric stepper (`0` = all available, or `10`, `50`, `100`).
- **Incremental Mode (`increase`)**: Toggle switch (`Download only works newer than local disk cache`).
- **Sorting Rule (`sort_by`)**: Dropdown options:
  - `play_count` (Most Viewed first)
  - `digg_count` (Most Liked first)
  - `create_time` (Newest first)
- **Sort Order (`reverse`)**: Toggle `Descending (Highest first)` vs `Ascending`.
- **Date Range Filter**: `start_time` and `end_time` date pickers (`YYYY-MM-DD`).

#### 5.2.4 Concurrency & Organization
- **Concurrent Worker Threads**: Slider from `1` to `32` (default `10`).
- **Directory Hierarchy (`folderstyle`)**:
  - `True`: `user_name/post/2026-03-01_title/video.mp4` (Isolated folder per video).
  - `False`: `user_name/post/2026-03-01_title.mp4` (Flat directory).

#### 5.2.5 Launch Payload
Submitting the form issues `POST /api/download`:
```json
{
  "link": ["https://v.douyin.com/8muR-7iUO6E/"],
  "path": "./Downloaded/",
  "music": true,
  "cover": true,
  "avatar": true,
  "json": false,
  "folderstyle": true,
  "database": true,
  "mode": ["post"],
  "thread": 10,
  "number": { "post": 0, "like": 0, "mix": 5 },
  "increase": { "post": false },
  "filter": { "sort_by": "play_count", "reverse": true, "limit": 0 }
}
```
The endpoint returns `{ "task_id": "task_20261006_001", "status": "running" }` and opens the Real-Time Progress Tracker.

---

## 6. Real-Time Progress Tracker Architecture

### 6.1 Server-Sent Events (SSE) Protocol

Instead of expensive polling, the frontend subscribes to an SSE stream:
`GET /api/tasks/{task_id}/stream?after_seq={lastSeq}`

```typescript
export interface TaskProgressEvent {
  seq: number;
  taskId: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  overall: {
    totalItems: number;
    completedItems: number;
    failedItems: number;
    totalBytes: number;
    downloadedBytes: number;
    speedBytesPerSec: number;
    elapsedSeconds: number;
    estimatedRemainingSeconds: number;
    percentage: number;
  };
  threads: Array<{
    threadId: number;
    status: 'idle' | 'fetching' | 'downloading' | 'writing';
    currentAwemeId?: string;
    currentDesc?: string;
    currentAssetType?: 'video' | 'music' | 'cover' | 'avatar' | 'json';
    itemTotalBytes?: number;
    itemDownloadedBytes?: number;
    itemSpeedBytesPerSec?: number;
  }>;
  recentFinished: Array<{
    awemeId: string;
    desc: string;
    filePath: string;
    sizeBytes: number;
    finishedAt: string;
  }>;
}
```

### 6.2 UI Components

1. **Overall Progress Card**:
   - Master progress bar (`h-3 bg-stone-100 rounded-full overflow-hidden`).
   - Bar fill: Terracotta gradient `bg-gradient-to-r from-amber-600 to-[#8D4B00] transition-all duration-300`.
   - Telemetry strip:
     - `Speed`: `12.4 MB/s` (JetBrains Mono font)
     - `Items`: `42 / 120 (35%)`
     - `Time`: `Elapsed: 01:24 | ETA: 02:40`
   - Actions: Pause, Resume, Stop/Cancel (`POST /api/tasks/{task_id}/cancel`).

2. **Active Worker Thread Pool Grid**:
   - Responsive grid (2 cols on tablet, 4-5 cols on desktop) visualizing each worker thread in the `ThreadPoolExecutor`.
   - Each thread card shows:
     - Worker index: `Thread #03` with a glowing indicator (emerald = downloading, amber = connecting, stone = idle).
     - Target Asset: Badged as `[Video]`, `[Audio]`, or `[Cover]`.
     - Chunk Progress: Mini progress bar showing individual file byte progress (`18.2 MB / 34.1 MB`).
     - Live throughput: `3.8 MB/s`.

3. **Live Completed Feed**:
   - Horizontal scrolling or compact vertical list of recently landed files.
   - Quick action: Click to preview in modal player or "Show in Folder".

---

## 7. Storage & Media Library View Architecture

### 7.1 Media Library Explorer

The Media Library view provides direct access to the downloaded contents without needing to navigate outside the browser.

#### 7.1.1 API Contract
- `GET /api/media`: Scans `./Downloaded/` directory and returns file list with hierarchical metadata.
- `GET /api/media/stream?file={path}`: Streams media binary with HTTP 206 Partial Content support (crucial for video scrub/seek).
- `POST /api/media/open-folder`: Instructs backend to open the host file manager.
- `DELETE /api/media?path={path}`: Removes file or folder.

#### 7.1.2 Media File Record Schema
```typescript
export interface MediaItem {
  id: string;
  path: string;
  relativePath: string;
  filename: string;
  mediaType: 'video' | 'audio' | 'image' | 'json';
  sizeBytes: number;
  createdAt: string;
  modifiedAt: string;
  authorNickname?: string;
  awemeId?: string;
  desc?: string;
  likesCount?: number;
  thumbnailUrl?: string; // Poster URL or local thumbnail stream
  streamUrl: string;     // /api/media/stream?path=...
}
```

#### 7.1.3 Explorer Layout
- **Toolbar**:
  - Filter chips: `All (142)`, `Videos (85)`, `Music (32)`, `Images (20)`, `JSON (5)`.
  - Search input: Real-time filter by title, author, or filename.
  - Sort selector: `Date Descending`, `Size Descending`, `Likes Descending`.
  - View switch: Grid cards (posters) vs Table view (dense file rows).
  - Primary Tool Button:
    ```tsx
    <button
      onClick={() => apiRequest('/api/media/open-folder', { method: 'POST' })}
      className="px-3 py-1.5 bg-white border border-stone-200 hover:border-amber-400 rounded-lg text-stone-700 font-bold text-xs flex items-center gap-1.5 shadow-2xs cursor-pointer"
    >
      <FolderOpen className="w-3.5 h-3.5 text-[#8D4B00]" />
      <span>Open in Explorer</span>
    </button>
    ```

### 7.2 In-Browser Audio & Video Preview Player

A dedicated player modal/drawer provides instant playback:
- **Video Player**: HTML5 `<video>` player styled with pyvideotrans controls.
- **Audio Player**: Waveform/bar visualization with play/pause and time scrub.
- **Features**:
  - Full range seeking via native HTTP 206 stream.
  - Playback speed switcher (`0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`).
  - Metadata inspector sidecard showing author, upload timestamp, digg count, and exact local disk path.
  - Download button to save file directly to browser downloads folder.

### 7.3 Windows File Explorer Backend Integration

In `douyinCommand.py` / backend service:
```python
import subprocess
import os
import platform

@app.post("/api/media/open-folder")
async def open_download_folder(req: OpenFolderRequest = None):
    target = Path(req.path if req and req.path else config.path).resolve()
    target.mkdir(parents=True, exist_ok=True)
    
    if platform.system() == "Windows":
        os.startfile(str(target))
    elif platform.system() == "Darwin":
        subprocess.run(["open", str(target)])
    else:
        subprocess.run(["xdg-open", str(target)])
    return {"status": "success", "opened": str(target)}
```

---

## 8. Settings & Cookie Management Specification

The Settings modal loads from and writes to `config.yaml` without corrupting YAML structure.

### 8.1 Configuration Fields Mapping

| YAML Field | Type | Default | UI Control | Description |
|---|---|---|---|---|
| `path` | `string` | `./Downloaded/` | Text Input + Browse | Root directory where downloads are saved |
| `thread` | `integer` | `10` | Slider (1–32) + Number box | Concurrent download workers in thread pool |
| `folderstyle` | `boolean` | `true` | Toggle Switch | Isolated folder per video (`true`) or flat (`false`) |
| `music` | `boolean` | `false` | Checkbox | Default toggle for extracting audio tracks |
| `cover` | `boolean` | `false` | Checkbox | Default toggle for downloading video cover posters |
| `avatar` | `boolean` | `false` | Checkbox | Default toggle for downloading author avatars |
| `json` | `boolean` | `false` | Checkbox | Default toggle for persisting raw JSON metadata |
| `database` | `boolean` | `false` | Toggle Switch | Enable SQLite database for incremental caching |
| `filter.sort_by`| `string` | `play_count` | Select Dropdown | Default sort metric (`play_count`, `digg_count`, `create_time`) |
| `filter.reverse`| `boolean` | `true` | Toggle Switch | Descending order (highest/newest first) |
| `cookies` | `dict` | Key-value pairs | Token Key-Value Inputs | Individual tokens: `msToken`, `ttwid`, `odin_tt`, `sid_guard` |
| `cookie` | `string` | Raw string | Textarea | Full cookie header string (takes higher priority) |

### 8.2 Cookie Management & Verification Engine

#### 8.2.1 Format Flexibility
1. **Key-Value Dictionary**:
   - `msToken`: Security token for web requests
   - `ttwid`: Web identity token (required for collection mixes)
   - `odin_tt`: User token (required for favorites and private lists)
   - `passport_csrf_token`: Session CSRF token
   - `sid_guard`: Session ID guard
2. **Raw Cookie String**:
   - Single multi-line textarea accepting browser-copied cookies (format `key1=val1; key2=val2;`).
   - Frontend auto-parses raw string into dictionary and vice-versa.

#### 8.2.2 Interactive Verification
The modal includes a "Test & Verify Cookie" button calling `POST /api/settings/verify-cookie`:
- Backend executes a lightweight probe against Douyin API (e.g. `Urls.USER_DETAIL` or `Urls.TAB_FEED`).
- Response returns:
  ```json
  {
    "valid": true,
    "userNickname": "User_29102",
    "expiresInDays": 42,
    "hasOdin": true,
    "hasTtwid": true,
    "warnings": []
  }
  ```
- If invalid: Displays friendly error explaining which token expired (e.g. `ttwid missing or expired; mix album fetching will fail`).

---

## 9. Production Build & FastAPI Integration Strategy

### 9.1 Static Files Mounting Architecture

The web application is packaged for zero-friction local execution. The Vite build generates standard static HTML/JS/CSS into `frontend/dist/`. FastAPI serves these files:

```python
# main_web.py
import sys
import webbrowser
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Douyin Downloader Web", version="1.0.0")

# CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
from src.api.routes import router as api_router
app.include_router(api_router, prefix="/api")

# Static mounting for production build
DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # Allow API calls to pass through
        if full_path.startswith("api/"):
            return None
        file_path = DIST_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")

def run():
    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    print(f"🚀 Starting Douyin Downloader Web on {url}")
    # Open browser on startup
    webbrowser.open(url)
    uvicorn.run("main_web:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    run()
```

### 9.2 Build Pipeline & Scripts
- Single-command dev environment:
  - Backend: `uvicorn main_web:app --reload --port 8000`
  - Frontend: `cd frontend && npm run dev` (proxies `/api` to port 8000)
- Single-command production build:
  - `cd frontend && npm run build` (outputs to `frontend/dist/`)
  - Run app: `python main_web.py` or launcher `python webui.py`

---

## 10. File Layout & Implementation Roadmap

### 10.1 Frontend Directory Structure

```
c:\Users\ddat2\Downloads\Projects\douyin-download\
├── frontend\
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── src\
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css                    <-- Warm editorial tokens (@theme)
│   │   ├── types\
│   │   │   ├── preview.ts               <-- Metadata, author, aweme schemas
│   │   │   ├── task.ts                  <-- Download config, progress, thread telemetry
│   │   │   ├── media.ts                 <-- Media files, filters, playback
│   │   │   └── settings.ts              <-- Config.yaml mappings, cookies
│   │   ├── api\
│   │   │   ├── client.ts                <-- Fetch wrapper with error handling
│   │   │   ├── parseApi.ts              <-- Link preview & resolution
│   │   │   ├── downloadApi.ts           <-- Start download & SSE stream subscription
│   │   │   ├── mediaApi.ts              <-- Media query, stream URL, open folder
│   │   │   └── settingsApi.ts           <-- Get/save config.yaml & verify cookie
│   │   ├── store\
│   │   │   ├── index.ts                 <-- Root Zustand store
│   │   │   ├── downloadSlice.ts         <-- Two-step state, current URL, active preview
│   │   │   ├── taskSlice.ts             <-- SSE subscription, active threads, progress
│   │   │   ├── mediaSlice.ts            <-- Media library items, filters, preview player
│   │   │   └── settingsSlice.ts         <-- Settings modal state, active tab
│   │   ├── components\
│   │   │   ├── layout\
│   │   │   │   ├── Header.tsx           <-- Branding, view tabs, settings trigger
│   │   │   │   ├── WorkflowStepper.tsx  <-- Step 1 (Preview) <-> Step 2 (Configure)
│   │   │   │   └── StatusFooter.tsx     <-- System status, active threads, speed
│   │   │   ├── downloader\
│   │   │   │   ├── Step1LinkPreview.tsx <-- Input bar & Preview Card
│   │   │   │   ├── Step2ConfigForm.tsx  <-- Mode, assets, filters, threads
│   │   │   │   ├── PreviewCard.tsx      <-- Author, thumbnail, stats card
│   │   │   │   ├── OverallProgress.tsx  <-- Big progress bar, ETA, speeds
│   │   │   │   └── ActiveThreadsGrid.tsx<-- Thread worker breakdown cards
│   │   │   ├── media\
│   │   │   │   ├── MediaLibraryView.tsx <-- Grid/table explorer
│   │   │   │   ├── MediaItemCard.tsx    <-- Card poster with badges
│   │   │   │   └── MediaPlayerModal.tsx <-- In-browser video/audio player
│   │   │   └── settings\
│   │   │       ├── SettingsModal.tsx    <-- Modal frame and tabs
│   │   │       ├── CookieTab.tsx        <-- Token fields + raw cookie + test button
│   │   │       ├── StorageTab.tsx       <-- Path, disk usage bar, folderstyle
│   │   │       └── ConcurrencyTab.tsx   <-- Threads, proxy, sort defaults
│   │   └── test\
│   │       └── ...
```

### 10.2 Implementation Milestones for Subsequent Agents

1. **Frontend Scaffolding**:
   - Initialize Vite + React 19 + TypeScript in `frontend/`.
   - Install `@tailwindcss/vite`, `tailwindcss`, `lucide-react`, `zustand`, `@radix-ui/*`.
   - Inject `@theme` with exact pyvideotrans color tokens into `src/index.css`.
2. **API Client & Store Setup**:
   - Create typed API client modules (`client.ts`, `parseApi.ts`, `downloadApi.ts`, `mediaApi.ts`, `settingsApi.ts`).
   - Create Zustand slices for clean reactive state.
3. **Two-Step Downloader Workflow**:
   - Implement `Step1LinkPreview` and `PreviewCard`.
   - Implement `Step2ConfigForm` with mode, assets, filters, and thread controls.
4. **Real-Time Progress & Worker Telemetry**:
   - Implement SSE listener in `taskSlice`.
   - Build `OverallProgress` and `ActiveThreadsGrid`.
5. **Media Library & Player**:
   - Build `MediaLibraryView` with grid/table views and "Open in Explorer" button.
   - Build `MediaPlayerModal` with HTML5 streaming and seek support.
6. **Settings & Cookie Manager**:
   - Build `SettingsModal` with cookie token inputs, raw parser, and verification hook.
7. **FastAPI Static Mount & Production Packaging**:
   - Configure `main_web.py` to serve `frontend/dist/` assets and SPA fallback.
