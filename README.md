<div align="center">

# 📥 Douyin Web Downloader & Automation Suite

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v3-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![n8n](https://img.shields.io/badge/n8n-Automation-EA4B71?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**An all-in-one solution for downloading watermark-free videos, images, photo albums, and audio from Douyin (抖音) with a modern Web UI and an end-to-end n8n automation pipeline.**

[Demo Video](https://youtu.be/XSQflGR09gA) • [Voice-over Demo](https://youtu.be/hOFfKV3Hjf4)

<br/>

<img width="950" alt="Douyin Web Downloader Dashboard" src="docs/images/webui_preview.png" />

</div>

---

## 🌟 Key Features

- 🖥️ **Unified Single-Screen Web UI**: Seamlessly integrates URL input, auto-preview extraction, download configuration, and real-time task telemetry on a single interactive screen.
- 🎬 **Comprehensive Douyin Content Support**:
  - Watermark-free Single Videos and Photo Albums (Note/Image sets) in original high definition (1080p/2K).
  - Creator profile bulk downloads (all posted works and liked videos).
  - Collections / Mixes (compilations) and soundtracks / original music.
  - Live stream recordings.
- ⚙️ **Custom Filename Template Engine**: Flexible template formatting with tokens such as `{date}_{title}_{id}`, `{likes}likes_{date}_{title}`, `{author}_{title}_{id}`, etc.
- ⚡ **High-Speed Multi-Threaded Engine**: Configurable concurrency (1 to 32 worker threads) with automatic exponential backoff retries and HTTP Range resume capabilities.
- 📊 **Real-Time Telemetry (Server-Sent Events)**: Live transmission speeds (MB/s), overall progress percentage, and individual thread worker monitors.
- 🤖 **Turnkey n8n Automation Pipeline**: Self-hosted n8n infrastructure on VPS, automated video downloads, AI caption rewrites, automated video translation & subtitle burn-in, and multi-platform publishing (YouTube, TikTok, Facebook).
- 🛡️ **Zero Credential Leakage**: User cookies, tokens, and API keys are strictly guarded by `.gitignore` and never committed to GitHub.

---

## 📂 Project Structure

```text
douyin-download/
├── docs/                      # Technical documentation, architecture & assets
│   └── images/                # Web UI dashboard screenshots & n8n pipeline diagrams
├── frontend/                  # React 19 + TypeScript + Vite user interface
│   ├── src/                   # Components (UnifiedDownloader, MediaLibrary, TaskTracker)
│   └── package.json
├── n8n/                       # 🤖 Complete n8n automation ecosystem
│   ├── setup/                 # VPS deployment infrastructure (Docker Compose, Dockerfile, Caddy, .env.example)
│   ├── workflows/             # Production-ready n8n workflow JSON exports (Download, AI Caption, Multi-platform Upload)
│   └── code/                  # Python video processing engine (FFmpeg, subtitle burn-in, audio sync)
├── src/                       # Backend service & core parsing engine
│   ├── douyin/                # Douyin API client, A-Bogus / X-Bogus token algorithms, file downloaders
│   └── web/                   # FastAPI REST APIs, SSE telemetry, task queue, settings manager
├── tests/                     # Automated test suites (Unit, Concurrency, E2E)
├── webui.py                   # Single-command launcher for the unified Web UI
├── douyinCommand.py           # Legacy command-line interface (CLI)
├── config.example.yml         # Configuration template
├── .cookies.example.json      # Cookie structure template
└── pyproject.toml             # uv package and dependency configuration
```

---

## 🚀 Quick Start

The project leverages **[`uv`](https://docs.astral.sh/uv/)** for fast, reliable package and environment management.

### 1. Clone the Repository

```bash
git clone https://github.com/datnndd/douyin-download.git
cd douyin-download
```

### 2. Environment Setup

**Using `uv` (Recommended):**
```bash
# uv automatically creates a virtual environment and synchronizes all dependencies
uv sync
```

*Or using traditional `pip`:*
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Launch the Web UI

Simply run:

```bash
uv run python webui.py
```

*(Or `python webui.py` if your virtual environment is already activated)*

Your default browser will automatically open to: `http://localhost:8000`.

To customize the host, port, or disable auto-opening the browser:
```bash
uv run python webui.py --port 8080 --host 0.0.0.0 --no-browser
```

---

## 🖥️ Web UI Walkthrough

<div align="center">
<img width="850" alt="Main Dashboard Interface" src="docs/images/webui_preview.png" />
</div>

1. **Enter Douyin URL**:
   - Paste any valid Douyin URL format: short links (`https://v.douyin.com/xxx/`), standard video links (`https://www.douyin.com/video/xxx`), creator profile links (`https://www.douyin.com/user/xxx`), or raw text copied from the Douyin mobile app containing Kouling (share codes). The system automatically cleans and extracts the target URL.
2. **Analyze & Preview**:
   - Click **Analyze & Preview** (or press `Enter`). The system fetches and renders a tailored preview card: creator avatar, nickname, follower count, total work count, title, and engagement stats.
3. **Configure Download Options**:
   - **Assets to Save**: Toggle MP4 videos, MP3 audios, cover images, creator avatars, or metadata JSON.
   - **Filename Template**: Select preset formulas or craft your custom token template.
   - **Date Range & Limits**: For author profiles, filter by publication date (`start_time`, `end_time`) and specify the maximum number of works to download.
   - **Folder Organization**: Group files by creator subfolders or save flat, with a one-click button to open the download folder in Windows Explorer.
4. **Start Download & Track Progress**:
   - Click **START DOWNLOAD**. The live telemetry drawer monitors download throughput (MB/s), percentage completed, and active worker thread statuses in real time.

---

## 🔒 Cookie Configuration & Credential Protection

> [!IMPORTANT]
> **Zero Credential Leakage**: `.cookies.json`, `config.yaml`, `config.yml`, and `.env` are strictly excluded in `.gitignore`. Your private cookies, tokens, and API keys will never be exposed to GitHub.

### How to Retrieve Douyin Cookies (Required for user profile downloads & HD streams):

1. Open your browser, navigate to [Douyin.com](https://www.douyin.com/), and log in to your account.
2. Press `F12` to open **Developer Tools**, then navigate to the **Network** tab.
3. Click any request made to `douyin.com` and locate **Request Headers** -> **Cookie**.
4. Copy the complete cookie string or primary keys (`msToken`, `ttwid`, `odin_tt`, `passport_csrf_token`, `sid_guard`).
5. Provide your cookie using either method:
   - **Method 1 (Direct via Web UI)**: Click the **Settings** icon in the top right corner of the Web UI, paste your cookie string into the Cookie field, and click **Save Settings**.
   - **Method 2 (Via Config File)**: Create `.cookies.json` following `.cookies.example.json` or configure `config.yaml`.

---

## 🤖 n8n Automation Pipeline

The end-to-end automation suite is modularly organized in the `n8n/` directory:

<div align="center">
<img width="850" alt="n8n Automation Pipeline Architecture" src="docs/images/n8n_pipeline_preview.png" />
</div>

### 1. `n8n/setup/` — VPS Infrastructure Deployment
- **`docker-compose.yml`**: Spins up containerized services including n8n, media processing engine (Python 3, FFmpeg, yt-dlp), Supabase Postgres database, and S3-compatible storage.
- **`Caddyfile`**: Reverse proxy with automated Let's Encrypt SSL/TLS certificates.
- **`Dockerfile`**: Customized n8n image pre-installed with multimedia processing binaries.
- **`.env.example`**: Secure environment variable template for credentials, database connections, and volume paths.

**Deployment on VPS:**
```bash
cd n8n/setup
cp .env.example .env
# Edit your domain name, credentials, and volume paths in .env
docker compose up -d --build
```

### 2. `n8n/workflows/` — Production Workflows
Pre-built, import-ready n8n workflows (JSON filenames map directly to n8n export IDs):
- **`download-video`** (`43UcYNxgLe1cFhJO.json`): Listens for incoming Webhooks, queries Douyin APIs, and downloads source media.
- **`translate_video`** (`translate_video.json`): Speech recognition pipeline, AI translation via Google Gemini / LLMs, and subtitle timestamp alignment.
- **`Rewrite Caption`** (`4ztsY8jthqi93eOg.json`): Generates engaging social media captions and SEO hashtags tailored for target platforms.
- **`Tiktok_Upload`** (`CRT2k3vvJYUgmhhh.json`), **`Youtube_Upload`** (`9V630z7TX1PtzYag.json`), **`Facebook_Upload`** (`OMkoDj41I7xhE4dh.json`): Automated publishing to TikTok, YouTube Shorts, and Facebook Reels.
- **`Tools / Backup WF`** (`JJZrYXoUevCmr4Zj.json`), **`Tool/Backup Credential`** (`M58qhLcPIQj3QfDj.json`): Automated backup of workflows and credentials to GitHub.
- **`Restore your workflows from GitHub`** (`YIuFcDeRfySsfgYU.json`), **`Restore your credentials from GitHub`** (`yrrGA1zqPuPnLSv1.json`): Automated restoration of workflows and credentials from GitHub.

### 3. `n8n/code/` — Video Processing Engine
- **`src/build_out.py`**: Python script executed within the container responsible for:
  - Concatenating TTS audio segments (PCM 24000Hz).
  - Burning styled subtitles onto video streams via FFmpeg.
  - Exporting web-ready output videos (`out.mp4`).

---

## 🧪 Testing & Verification

The project includes comprehensive test suites with 100% pass coverage:

```bash
# Run all 194 E2E backend test cases:
uv run python tests/run_tests.py

# Verify React 19 production build:
cd frontend
npm run build
```

---

## 🔗 Supported URL Formats

| Content Type | Example URL Structure |
| :--- | :--- |
| **Single Video / Photo Album** | `https://v.douyin.com/xxxxx/`<br/>`https://www.douyin.com/video/xxxxx`<br/>`https://www.douyin.com/note/xxxxx` |
| **Creator Profile** | `https://www.douyin.com/user/MS4wLjABAAAA...` |
| **Collection / Mix** | `https://www.douyin.com/collection/xxxxx` |
| **Soundtrack / Music** | `https://www.douyin.com/music/xxxxx` |
| **Live Stream** | `https://live.douyin.com/xxxxx` |

---

## 🙏 Credits & Acknowledgments

This project is built and expanded upon foundations from [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader). Sincere thanks to the original author for their contributions to the open-source community.

<div align="center">

### ⭐ Star this repository if you find it helpful!

</div>
