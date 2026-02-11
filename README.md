<div align="center">

# 📥 Douyin Download

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20MacOS-blue?style=for-the-badge)]()

**A powerful tool for scraping and downloading videos, images, and livestreams from Douyin (抖音)**

[Demo Video](https://youtu.be/XSQflGR09gA) • [Voice-over Demo](https://youtu.be/hOFfKV3Hjf4)

<img width="800" alt="Douyin Download Demo" src="https://github.com/user-attachments/assets/bf0167c9-0965-4dc6-848d-ae6bb66c7e5f" />

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📹 **Video Download** | Download all videos/images from a user profile |
| ❤️ **Liked Videos** | Support downloading liked videos (requires cookie) |
| 🎶 **Music & Collection** | Download by music or collection (合集) |
| 🔴 **Livestream** | Support downloading livestreams |

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/datnndd/douyin-download.git
cd douyin-download
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Program

```bash
python douyinCommand.py --config config.yaml
```

---

## 🍪 Cookie Configuration (Optional)

> [!TIP]
> Using a cookie allows you to fetch more detailed information from the API.

### How to Get Your Cookie

1. Open **Douyin Web** in your browser
2. Log in to your account
3. Open **DevTools** (`F12`) → **Network** tab
4. Find the `Cookie` field in the request header
5. Copy the following values and add them to `config.yaml`:

```yaml
msToken: "your_value"
ttwid: "your_value"
odin_tt: "your_value"
passport_csrf_token: "your_value"
sid_guard: "your_value"
```

---

## 🔗 Supported Links

### 🎬 Video / Images
| Type | URL Pattern |
|------|-------------|
| Share Link | `https://v.douyin.com/xxxxx/` |
| Direct Link | `https://www.douyin.com/video/xxxxx` |
| Image Posts | `https://www.douyin.com/note/xxxxx` |

### 👤 User Profile
| Type | URL Pattern |
|------|-------------|
| Profile Page | `https://www.douyin.com/user/xxxxx` |
| Posted Works | Download all posted works |
| Liked Works | Download all liked works (requires permission) |

### 📚 Collection & Music
| Type | URL Pattern |
|------|-------------|
| Collection | `https://www.douyin.com/collection/xxxxx` |
| Music | `https://www.douyin.com/music/xxxxx` |

### 🔴 Livestream
| Type | URL Pattern |
|------|-------------|
| Live Room | `https://live.douyin.com/xxxxx` |

---

## 🙏 Credits

> This project is referenced from [jiji262/douyin-downloader](https://github.com/jiji262/douyin-downloader).  
> Thanks to the original author for sharing the source code.

---

<div align="center">

### ⭐ Star this repo if you find it useful!

**Made with ❤️ for the community**

</div>
