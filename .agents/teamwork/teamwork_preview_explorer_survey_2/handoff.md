# Handoff Report: Frontend Architecture & Design System Survey
**Agent:** Codebase Explorer (Frontend Architect)  
**Date:** 2026-10-06  
**Type:** Hard Handoff (Investigation & Architecture Survey Complete)

---

## 1. Observation

1. **Reference Design System in Pyvideotrans**:
   - Inspected `c:\Users\ddat2\Downloads\Projects\pyvideotrans\frontend\src\index.css` (lines 1–23):
     ```css
     @import "tailwindcss";

     @theme {
       --color-surface: #FAF8F5;
       --color-surface-container: #F3ECE2;
       --color-surface-container-low: #FAF6F0;
       --color-surface-container-high: #EDE5DA;
       --color-surface-container-lowest: #FFFFFF;
       --color-on-surface: #1F2328;
       --color-on-surface-variant: #595E68;
       --color-outline: #898174;
       --color-outline-variant: #E5DED4;
       --color-primary: #8D4B00;
       --color-primary-hover: #743D00;
       --color-primary-container: #B15F00;
       --color-primary-light: #FFDCC3;
       --color-on-primary: #FFFFFF;
       --color-secondary: #A13E28;
       --color-tertiary: #506053;

       --font-sans: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
       --font-mono: "JetBrains Mono", ui-monospace, monospace;
     }
     ```
   - Inspected `pyvideotrans/frontend/package.json` (lines 12–27, 29–34):
     Uses React 19 (`react: ^19.0.0`, `react-dom: ^19.0.0`), Vite 6 (`vite: ^6.2.0`), `@tailwindcss/vite: ^4.0.9`, `@radix-ui/*`, `lucide-react: ^1.16.0`, and Zustand 5 (`zustand: ^5.0.3`).
   - Inspected `pyvideotrans/frontend/src/components/Header.tsx` (lines 14–47):
     Uses fixed header `h-[50px]`, ivory surfaces, pill navigation tab bars (`bg-stone-100/80 rounded-lg p-0.5`), and active tab styling (`bg-white text-[#8D4B00] font-bold shadow-2xs border border-amber-200/80`).
   - Inspected `pyvideotrans/frontend/src/components/settings/SettingsModal.tsx` and `StorageTab.tsx` (lines 62–100):
     Demonstrates dual tab navigation, rounded container frames (`rounded-2xl shadow-2xl border border-stone-200`), disk usage visualization bars, and form input layouts.

2. **Douyin Downloader Engine & Configuration**:
   - Inspected `c:\Users\ddat2\Downloads\Projects\douyin-download\config.yaml` (lines 20–116):
     Contains options: `path` (`./Downloaded/`), `music` (`False`), `cover` (`False`), `avatar` (`False`), `json` (`False`), `folderstyle` (`False`), `mode` (`["post"]`), `number` (`post`, `like`, `allmix`, `mix`, `music`), `database` (`False`), `increase` (`post`, `like`, etc.), `thread` (`10`), `filter` (`sort_by`, `reverse`, `limit`), `cookies` (dictionary with `msToken`, `ttwid`, `odin_tt`, `passport_csrf_token`, `sid_guard`), and `cookie` (raw string format).
   - Inspected `c:\Users\ddat2\Downloads\Projects\douyin-download\douyinCommand.py` (lines 292–308, 311–450):
     `DouyinClient` uses `self.api.getKey(url)` returning `(key_type, key)` with handlers for `aweme`, `user`, `mix`, `music`, and `live`.
   - Inspected `c:\Users\ddat2\Downloads\Projects\douyin-download\src\douyin\download.py` (lines 27–37, 80–148, 160–187, 377–436):
     `Download` uses `ThreadPoolExecutor(max_workers=self.thread)` to download media files (video, images, music, cover, avatar, json) with resume support (`Range: bytes={file_size}-`), retries with exponential backoff, and chunk-based writing (`chunk_size=8192`).

3. **Current Frontend Status**:
   - Checked `c:\Users\ddat2\Downloads\Projects\douyin-download\frontend`:
     Directory does not exist yet. Needs to be scaffolded with Vite + React 19 + TypeScript + Tailwind CSS v4.

---

## 2. Logic Chain

1. **Styling Parity (Observation 1 ➔ Logic 1)**:
   The user explicitly requested the warm editorial aesthetic of pyvideotrans (`ORIGINAL_REQUEST.md`). Directly porting the Tailwind CSS v4 `@theme` configuration and typography guarantees visual consistency with warm ivory surfaces (`#FAF8F5`), terracotta buttons (`#8D4B00`), and warm card borders (`#E7E4DC`), preventing generic Tailwind/Bootstrap appearance.

2. **Interaction Flow Alignment (Observation 1 & 2 ➔ Logic 2)**:
   Douyin links encompass multiple distinct entity types (single video `aweme`, user profile `user`, collection `mix`, audio `music`, live stream `live`). The CLI previously forced users to configure everything in `config.yaml` before running. Dividing the web workflow into:
   - **Step 1 (Link Preview)**: Calls `DouyinApi.getKey(url)` and immediately displays author avatar, nickname, video thumbnail, title, and statistics.
   - **Step 2 (Configuration & Launch)**: Exposes tailored options based on the detected link type (e.g. `mode: [post, like, mix]` for user profiles; asset toggles; sorting filters; thread count).
   This eliminates invalid CLI runs and gives users confidence that the target was correctly identified before downloading gigabytes of media.

3. **Concurrency Telemetry & SSE (Observation 2 ➔ Logic 3)**:
   The backend download engine uses multi-threaded downloads (`ThreadPoolExecutor`). A simple single progress percentage would fail to communicate thread stalls or network throttles. Implementing an active thread pool visualizer (workers 1..N) backed by Server-Sent Events (SSE) allows the frontend to show each worker downloading its specific file chunk and current transfer rate in real-time.

4. **Media Library & Desktop Bridge (Observation 2 & 3 ➔ Logic 4)**:
   Downloaded files land in `./Downloaded/` with folder hierarchies (`folderstyle`). Providing an in-browser media player with HTTP 206 Partial Content Range streaming allows users to preview video/audio immediately. Pairing this with a backend endpoint invoking `os.startfile` on Windows bridges the web interface with local desktop file management as requested in R3.

5. **Settings & Production Deployment (Observation 2 ➔ Logic 5)**:
   The settings interface directly maps all fields of `config.yaml` with dual-mode cookie editing (structured token fields and raw string) and a live verification probe. In production, FastAPI statically serves the compiled Vite assets (`frontend/dist`) via `main_web.py`, enabling single-command startup (`python webui.py`).

---

## 3. Caveats

1. **Douyin Anti-Scraping / WAF**:
   Link preview and downloads depend on valid cookies (`msToken`, `ttwid`, `odin_tt`). If Douyin alters API parameters or imposes Captchas, the preview card must gracefully display an actionable prompt alerting the user to refresh cookies in the Settings modal.
2. **Local Desktop vs Remote Server**:
   The "Open in Explorer" button uses `os.startfile(path)` which executes on the host running the FastAPI backend. In a local desktop environment (the stated use case), this immediately pops up Windows File Explorer. If deployed on a headless remote Linux server, this action should fall back to a direct browser download.
3. **Tailwind CSS Version**:
   The reference project uses `@tailwindcss/vite` v4 (`@theme` syntax in `index.css`). The frontend scaffolding must use Tailwind CSS v4 (not v3 `tailwind.config.js`) to seamlessly utilize these tokens.

---

## 4. Conclusion

The frontend architecture and design system survey is complete. The application is designed as a desktop-class Single Page Application (SPA) with:
1. Warm editorial aesthetic matching pyvideotrans using exact Tailwind v4 design tokens.
2. Two-step download flow (Link Preview Card ➔ Configuration & Download Launch).
3. Real-time progress tracker with global telemetry and an active multi-thread worker breakdown.
4. Storage & Media Library with in-browser HTML5 video/audio playback and "Open in Explorer" capability.
5. Lossless `config.yaml` settings management with cookie parsing and interactive validation.
6. Seamless production build serving via FastAPI static mounting.

Detailed architectural specifications, component trees, API contracts, and implementation blueprints are documented in `report.md`.

---

## 5. Verification Method

To verify the architecture survey and design tokens:
1. **Verify Design System Extraction**:
   - Inspect `pyvideotrans/frontend/src/index.css` and confirm theme variable definitions match Section 2 of `report.md`.
2. **Verify Component Hierarchy**:
   - Review Section 4 of `report.md` against requirements in `ORIGINAL_REQUEST.md` (R1–R4).
3. **Verify API Contract Alignment**:
   - Verify that all endpoints referenced in `report.md` (`/api/parse`, `/api/download`, `/api/tasks/{task_id}/stream`, `/api/media`, `/api/media/open-folder`, `/api/settings`) map directly to the Douyin download engine functions in `src/douyin/` and `douyinCommand.py`.
4. **Invalidation Conditions**:
   - If the project requires Tailwind v3 instead of v4, `@theme` syntax must be translated to `tailwind.config.js`.
   - If the backend chooses WebSockets instead of SSE, the stream subscriber in `taskSlice` should be updated accordingly (SSE was chosen to match pyvideotrans pattern).
