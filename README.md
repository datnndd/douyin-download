 📥 douyin-download  

**douyin-download** is a tool for **scraping and downloading** videos, images, livestreams, and more from **Douyin (抖音)**.  

---

## 🚀 Features  
- 📹 Download all **videos/images** from a user  
- ❤️ Support downloading **liked videos** (requires cookie)  
- 🎶 Support downloading by **music** or **collection (合集)**  
- 🔴 Support downloading **livestreams**  

---

## 🔧 Installation  

### 1️⃣ Clone the repo  
```bash  
git clone https://github.com/datnndd/douyin-download.git  
cd douyin-download
```
  
### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```
 
### 3️⃣ Configure Cookie (optional)
*⚠️ Using a cookie allows you to fetch more detailed information from the API.*

**How to get the cookie:**
  1. Open Douyin Web in your browser
  2. Log in to your account
  3. Open DevTools (F12) → Network tab
  4. Find the Cookie field in the request header
  5. Copy the following values and add them to config.yaml:
     msToken
     ttwid
     odin_tt
     passport_csrf_token
     sid_guard

### 4️⃣ Run the program
Edit config.yaml as needed, then run:
```bash
python douyinCommand.py --config config.yaml
```

### 📝 Supported Links
**🎬 Video / Images**
  - Video share link: https://v.douyin.com/xxxxx/
  - Direct video link: https://www.douyin.com/video/xxxxx
  - Image posts (图集): https://www.douyin.com/note/xxxxx

**👤 User**
  - Profile page: https://www.douyin.com/user/xxxxx
  - Download all posted works
  - Download all liked works (user permission)

**📚 Collection**
  - Collection: https://www.douyin.com/collection/xxxxx
  - Music: https://www.douyin.com/music/xxxxx

**🔴 Livestream**
  - Livestream room: https://live.douyin.com/xxxxx

## 🙏 Referenced
Code referenced from jiji262/douyin-downloader.
Thanks to the author for sharing the source code.

## ✨ Happy downloading Douyin videos!
