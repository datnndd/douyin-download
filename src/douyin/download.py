#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Any
from pathlib import Path
import logging
import random

import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.douyin import douyin_headers
from src.common import utils


logger = logging.getLogger(__name__)


class Download(object):
    def __init__(self, thread=5, music=True, cover=True, avatar=True, resjson=True, folderstyle=True):
        self.thread = thread
        self.music = music
        self.cover = cover
        self.avatar = avatar
        self.resjson = resjson
        self.folderstyle = folderstyle
        self.retry_times = 5
        self.chunk_size = 8192
        self.timeout = 60

        self._tls = threading.local()

    def _get_session(self) -> requests.Session:
        s = getattr(self._tls, "session", None)
        if s is None:
            s = requests.Session()
            retries = Retry(
                total=2,
                backoff_factor=0.2,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            self._tls.session = s
        return s

    def _download_media(self, url: str, path: Path, desc: str) -> bool:
        """Download for all kind of media"""
        if path.exists():
            logger.info(f"File Exited: {desc}")
            return True

        return self.download_with_resume(url, path, desc)

    def _get_first_url(self, url_list: list) -> Any | None:
        """Get the first URL"""
        if isinstance(url_list, list) and len(url_list) > 0:
            return url_list[0]
        return None

    def _download_single_media(self, media_info: dict) -> bool:
        try:
            url = media_info['url']
            path = media_info['path']
            desc = media_info['desc']
            return self._download_media(url, path, desc)
        except Exception as e:
            logger.error(f"Download media failed: {media_info.get('desc', 'Unknown')}, Error: {str(e)}")
            return False

    def _prepare_media_tasks(self, aweme: dict, path: Path, name: str, desc: str) -> List[dict]:
        tasks = []

        try:
            if aweme["awemeType"] == 0:  # Video
                video_path = path / f"{name}_video.mp4"
                url_list = aweme.get("video", {}).get("play_addr", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    tasks.append({
                        'url': url,
                        'path': video_path,
                        'desc': f"[Video]{desc}",
                        'type': 'video'
                    })
                else:
                    logger.warning(f"Empty Video URL : {desc}")

            elif aweme["awemeType"] == 1:  # Images
                for i, image in enumerate(aweme.get("images", [])):
                    url_list = image.get("url_list", [])
                    if url := self._get_first_url(url_list):
                        image_path = path / f"{name}_image_{i}.jpeg"
                        tasks.append({
                            'url': url,
                            'path': image_path,
                            'desc': f"[Image {i + 1}]{desc}",
                            'type': 'image'
                        })
                    else:
                        logger.warning(f"Images {i + 1} URL empty: {desc}")

            if self.music:
                url_list = aweme.get("music", {}).get("play_url", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    music_name = utils.replaceStr(aweme["music"]["title"])
                    music_path = path / f"{name}_music_{music_name}.mp3"
                    tasks.append({
                        'url': url,
                        'path': music_path,
                        'desc': f"[Nhạc]{desc}",
                        'type': 'music'
                    })

            if self.cover and aweme["awemeType"] == 0:
                url_list = aweme.get("video", {}).get("cover", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    cover_path = path / f"{name}_cover.jpeg"
                    tasks.append({
                        'url': url,
                        'path': cover_path,
                        'desc': f"[Cover]{desc}",
                        'type': 'cover'
                    })

            if self.avatar:
                url_list = aweme.get("author", {}).get("avatar", {}).get("url_list", [])
                if url := self._get_first_url(url_list):
                    avatar_path = path / f"{name}_avatar.jpeg"
                    tasks.append({
                        'url': url,
                        'path': avatar_path,
                        'desc': f"[Avatar]{desc}",
                        'type': 'avatar'
                    })

        except Exception as e:
            logger.error(f"Prepare task download : {str(e)}")

        return tasks

    def _download_media_files_threaded(self, aweme: dict, path: Path, name: str, desc: str) -> bool:
        tasks = self._prepare_media_tasks(aweme, path, name, desc)

        if not tasks:
            logger.warning(f"No media file for download: {desc}")
            return True

        success_count = 0
        failed_tasks = []

        with ThreadPoolExecutor(max_workers=self.thread) as executor:
            # Submit all of tasks
            future_to_task = {executor.submit(self._download_single_media, task): task for task in tasks}

            # Processing with progress bar
            with tqdm(total=len(tasks), desc=f"Downloading media for {desc[:20]}...") as pbar:
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                        else:
                            failed_tasks.append(task)
                    except Exception as e:
                        logger.error(f"Task download exception: {task['desc']}, lỗi: {str(e)}")
                        failed_tasks.append(task)
                    finally:
                        pbar.update(1)

        # Log result
        if failed_tasks:
            logger.warning(f"Download Fail: {desc}:")
            for task in failed_tasks:
                logger.warning(f"  - {task['desc']} ({task['type']})")

        logger.info(f"Download media success: {success_count}/{len(tasks)} : {desc}")
        return len(failed_tasks) == 0

    def _rename_if_exists(self, save_path: Path, file_name: str, suffix: str) -> None:
        """
        Check if a file/folder with the same suffix (time + desc) exists but with different likes count.
        If found, rename it to the new file_name.
        """
        try:
            # Search for files/folders ending with the same suffix
            # Pattern: *likes_{suffix}
            # Suffix is like: 2025-09-02 22.09.04_Desc
            # Full name: 000029183likes_2025-09-02 22.09.04_Desc

            # We need to be careful not to match random files, so we expect a digit prefix
            # glob pattern: *likes_{suffix}
            # Note: file_name already contains the suffix.
            # safe_name ensures no special chars, but glob might need escaping if [] used?
            # utils.replaceStr keeps alphanumeric and chinese, so usually safe for glob found in utils.

            # We look for ANY file ending with this suffix
            # However, glob might be slow if directory is huge.
            # But usually it's per-user folder.

            search_pattern = f"*likes_{suffix}"
            if self.folderstyle:
                # We are looking for a folder
                candidates = list(save_path.glob(search_pattern))
            else:
                # We are looking for files starting with *likes_{suffix}*.mp4 or similar?
                # Actually download creates multiple files: _video.mp4, _cover.jpeg...
                # If folderstyle=False, all files are in save_path.
                # We should look for the video file primarily?
                # Or just any file that matches the base name pattern?

                # Let's look for the base name.
                # If folderstyle=False, we have files like:
                # {name}_video.mp4
                # {name}_cover.jpeg
                # {name}_result.json
                # We need to rename ALL of them.

                # This is complicated for folderstyle=False because we have multiple files.
                # Strategy: Identify the old base name from one file (e.g. video), then rename all related files.
                candidates = list(save_path.glob(f"*{suffix}_video.mp4"))

            if not candidates:
                return

            # Found candidate(s). Take the first one.
            old_path = candidates[0]
            old_name = old_path.name

            # Extract old base name
            if self.folderstyle:
                if old_name == file_name:
                    return # Already correct
                old_base_name = old_name
            else:
                # old_name is like "0000100likes_..._video.mp4"
                # We want "0000100likes_..."
                old_base_name = old_name.replace("_video.mp4", "")
                if old_base_name == file_name:
                    return

            logger.info(f"🔄 Found existing content with different name. Renaming: {old_base_name} -> {file_name}")

            if self.folderstyle:
                # Rename directory
                new_path = save_path / file_name
                if not new_path.exists():
                    try:
                        old_path.rename(new_path)
                    except OSError as e:
                         logger.warning(f"Rename failed: {e}")
            else:
                # Rename all files starting with old_base_name
                for f in save_path.glob(f"{old_base_name}*"):
                     new_name = f.name.replace(old_base_name, file_name)
                     try:
                         f.rename(save_path / new_name)
                     except OSError:
                         pass

        except Exception as e:
            logger.warning(f"Error checking/renaming existing file: {e}")

    def awemeDownload(self, awemeDict: dict, savePath: Path) -> bool:
        """Download detail of video with multithread"""
        if not awemeDict:
            logger.warning("Video data not suitable")
            return False

        try:
            # Tạo thư mục lưu trữ
            save_path = Path(savePath)
            save_path.mkdir(parents=True, exist_ok=True)

            # Get digg_count for filename with zero-padding for proper sorting
            digg_count = awemeDict.get('statistics', {}).get('digg_count', 0)
            digg_count_str = f"{digg_count:09d}"  # 9-digit zero-padding for sorting

            # Tạo tên file từ thời gian, digg_count và mô tả
            # Identify suffix for stable identification: time + desc
            suffix_id = f"{awemeDict['create_time']}_{utils.replaceStr(awemeDict['desc'])}"
            file_name = f"{digg_count_str}likes_{suffix_id}"

            # Check and rename if exists
            self._rename_if_exists(save_path, file_name, suffix_id)

            aweme_path = save_path / file_name if self.folderstyle else save_path
            aweme_path.mkdir(exist_ok=True)

            # Lưu dữ liệu JSON với định dạng mới
            if self.resjson:
                self._save_json(aweme_path / f"{file_name}_result.json", awemeDict)

            # Download các file media sử dụng threading
            desc = file_name[:30]
            success = self._download_media_files_threaded(awemeDict, aweme_path, file_name, desc)

            if success:
                logger.info(f"✅ Download success: {desc}")
            else:
                logger.warning(f"⚠️ Download success with some errors: {desc}")

            return success

        except Exception as e:
            logger.error(f"Video Error: {str(e)}")
            return False

    def _save_json(self, path: Path, data: dict) -> None:
        """Save JSON"""
        try:
            with open(path, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Save JSON: {path}")
        except Exception as e:
            logger.error(f"Save JSON failed: {path}, Error: {str(e)}")

    def userDownload(self, awemeList: List[dict], savePath: Path):
        """Download all aweme of user with threading"""
        if not awemeList:
            logger.warning("⚠️ Can't find aweme for downloading")
            return

        save_path = Path(savePath)
        save_path.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        total_count = len(awemeList)
        success_count = 0

        logger.info(f"Start download {total_count} video...")
        logger.info(f"Save at: {save_path}")
        logger.info(f"Number of thread: {self.thread}")

        with ThreadPoolExecutor(max_workers=min(self.thread, total_count)) as executor:
            future_to_aweme = {
                executor.submit(self.awemeDownload, aweme, save_path): aweme
                for aweme in awemeList
            }

            with tqdm(total=total_count, desc="Processing videos") as pbar:
                for future in as_completed(future_to_aweme):
                    aweme = future_to_aweme[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                    except Exception as e:
                        aweme_id = aweme.get('aweme_id', 'Unknown')
                        logger.error(f"❌ Download failed, aweme_id {aweme_id}: {str(e)}")
                    finally:
                        pbar.update(1)

        # Thống kê kết quả
        end_time = time.time()
        duration = end_time - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)

        logger.info(f"\n=== DONE ===")
        logger.info(f"Success: {success_count}/{total_count}")
        logger.info(f"Time: {minutes}phút {seconds}giây")
        logger.info(f"Save at: {save_path}")

        if success_count < total_count:
            logger.warning(f"{total_count - success_count} video download failed")

    def download_with_resume(self, url: str, filepath: Path, desc: str) -> bool:
        """Download with support resume (continue download when interrupted)"""
        file_size = filepath.stat().st_size if filepath.exists() else 0
        headers = {'Range': f'bytes={file_size}-'} if file_size > 0 else {}

        for attempt in range(self.retry_times):
            try:
                # Create fresh session on retry to avoid stale connections
                if attempt > 0:
                    self._tls.session = None

                session = self._get_session()
                response = session.get(url, headers={**douyin_headers, **headers},
                                        stream=True, timeout=self.timeout)

                if response.status_code not in (200, 206):
                    raise Exception(f"HTTP {response.status_code}")

                total_size = int(response.headers.get('content-length', 0))
                # If server returns 200 (full content), content-length is total file size
                # If server returns 206 (partial), content-length is remaining bytes
                if response.status_code == 206:
                    total_size += file_size
                mode = 'ab' if file_size > 0 and response.status_code == 206 else 'wb'

                logger.debug(f"⬇️ Downloading {desc}...")

                with open(filepath, mode) as f:
                    with tqdm(total=total_size, initial=file_size, unit='B',
                              unit_scale=True, desc=desc[:20], leave=False) as pbar:
                        try:
                            for chunk in response.iter_content(chunk_size=self.chunk_size):
                                if chunk:
                                    size = f.write(chunk)
                                    pbar.update(size)
                        except (requests.exceptions.ConnectionError,
                                requests.exceptions.ChunkedEncodingError,
                                Exception) as chunk_error:
                            current_size = filepath.stat().st_size if filepath.exists() else 0
                            logger.warning(f"Interrupted when download: {current_size} bytes: {str(chunk_error)}")
                            raise chunk_error

                logger.debug(f"✅ Success: {desc}")
                return True

            except Exception as e:
                wait_time = min(2 ** (attempt + 1), 10) + random.uniform(0, 1)
                logger.warning(f"Download Failed ({attempt + 1}/{self.retry_times}): {str(e)}")

                if attempt == self.retry_times - 1:
                    logger.error(f"❌ Download Failed: {desc}\n   {str(e)}")
                    return False
                else:
                    logger.info(f"Wait {wait_time:.1f}s to try again...")
                    time.sleep(wait_time)
                    # Re-check file size for resume on retry
                    file_size = filepath.stat().st_size if filepath.exists() else 0
                    headers = {'Range': f'bytes={file_size}-'} if file_size > 0 else {}

        return False


if __name__ == "__main__":
    pass