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

from src.douyin import douyin_headers
from src.common import utils


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("douyin_downloader")


class Download(object):
    def __init__(self, thread=5, music=True, cover=True, avatar=True, resjson=True, folderstyle=True):
        self.thread = thread
        self.music = music
        self.cover = cover
        self.avatar = avatar
        self.resjson = resjson
        self.folderstyle = folderstyle
        self.retry_times = 3
        self.chunk_size = 8192
        self.timeout = 30

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
                    logger.warning(f"Video URL rỗng: {desc}")

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
            logger.warning(f"Một số file download thất bại cho {desc}:")
            for task in failed_tasks:
                logger.warning(f"  - {task['desc']} ({task['type']})")

        logger.info(f"Download media hoàn thành: {success_count}/{len(tasks)} thành công cho {desc}")
        return len(failed_tasks) == 0

    def awemeDownload(self, awemeDict: dict, savePath: Path) -> bool:
        """Download detail of video with multithread"""
        if not awemeDict:
            logger.warning("Dữ liệu video không hợp lệ")
            return False

        try:
            # Tạo thư mục lưu trữ
            save_path = Path(savePath)
            save_path.mkdir(parents=True, exist_ok=True)

            # Tạo tên file từ thời gian và mô tả
            file_name = f"{awemeDict['create_time']}_{utils.replaceStr(awemeDict['desc'])}"
            aweme_path = save_path / file_name if self.folderstyle else save_path
            aweme_path.mkdir(exist_ok=True)

            # Lưu dữ liệu JSON với định dạng mới
            if self.resjson:
                self._save_json(aweme_path / f"{file_name}_result.json", awemeDict)

            # Download các file media sử dụng threading
            desc = file_name[:30]
            success = self._download_media_files_threaded(awemeDict, aweme_path, file_name, desc)

            if success:
                logger.info(f"✅ Download hoàn thành: {desc}")
            else:
                logger.warning(f"⚠️ Download hoàn thành với một số lỗi: {desc}")

            return success

        except Exception as e:
            logger.error(f"Xử lý video lỗi: {str(e)}")
            return False

    def _save_json(self, path: Path, data: dict) -> None:
        """Lưu dữ liệu JSON ra file"""
        try:
            with open(path, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Đã lưu JSON: {path}")
        except Exception as e:
            logger.error(f"Lưu JSON thất bại: {path}, lỗi: {str(e)}")


    def userDownload(self, awemeList: List[dict], savePath: Path):
        """Download hàng loạt video của một user sử dụng threading"""
        if not awemeList:
            logger.warning("⚠️ Không tìm thấy nội dung để download")
            return

        save_path = Path(savePath)
        save_path.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        total_count = len(awemeList)
        success_count = 0

        logger.info(f"Bắt đầu download {total_count} video...")
        logger.info(f"Đường dẫn lưu: {save_path}")
        logger.info(f"Số thread: {self.thread}")

        # Sử dụng ThreadPoolExecutor cho việc download từng aweme
        with ThreadPoolExecutor(max_workers=min(self.thread, total_count)) as executor:
            # Submit tất cả các task download
            future_to_aweme = {
                executor.submit(self.awemeDownload, aweme, save_path): aweme
                for aweme in awemeList
            }

            # Xử lý kết quả với progress bar
            with tqdm(total=total_count, desc="Processing videos") as pbar:
                for future in as_completed(future_to_aweme):
                    aweme = future_to_aweme[future]
                    try:
                        success = future.result()
                        if success:
                            success_count += 1
                    except Exception as e:
                        aweme_id = aweme.get('aweme_id', 'Unknown')
                        logger.error(f"❌ Download thất bại aweme_id {aweme_id}: {str(e)}")
                    finally:
                        pbar.update(1)

        # Thống kê kết quả
        end_time = time.time()
        duration = end_time - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)

        logger.info(f"\n=== HOÀN THÀNH ===")
        logger.info(f"Thành công: {success_count}/{total_count}")
        logger.info(f"Thời gian: {minutes}phút {seconds}giây")
        logger.info(f"Lưu tại: {save_path}")

        if success_count < total_count:
            logger.warning(f"Có {total_count - success_count} video download thất bại")

    def download_with_resume(self, url: str, filepath: Path, desc: str) -> bool:
        """Download với hỗ trợ resume (tiếp tục download khi bị gián đoạn)"""
        file_size = filepath.stat().st_size if filepath.exists() else 0
        headers = {'Range': f'bytes={file_size}-'} if file_size > 0 else {}

        for attempt in range(self.retry_times):
            try:
                response = requests.get(url, headers={**douyin_headers, **headers},
                                        stream=True, timeout=self.timeout)

                if response.status_code not in (200, 206):
                    raise Exception(f"HTTP {response.status_code}")

                total_size = int(response.headers.get('content-length', 0)) + file_size
                mode = 'ab' if file_size > 0 else 'wb'

                logger.debug(f"⬇️ Downloading {desc}...")

                with open(filepath, mode) as f:
                    # Sử dụng tqdm cho progress bar của từng file
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
                            # Mạng bị gián đoạn, ghi lại kích thước file hiện tại
                            current_size = filepath.stat().st_size if filepath.exists() else 0
                            logger.warning(f"Download bị gián đoạn, đã tải {current_size} bytes: {str(chunk_error)}")
                            raise chunk_error

                logger.debug(f"✅ Hoàn thành: {desc}")
                return True

            except Exception as e:
                # Thời gian chờ retry (exponential backoff)
                wait_time = min(2 ** attempt, 10)  # Tối đa 10 giây
                logger.warning(f"Download thất bại (lần {attempt + 1}/{self.retry_times}): {str(e)}")

                if attempt == self.retry_times - 1:
                    logger.error(f"❌ Download thất bại: {desc}\n   {str(e)}")
                    return False
                else:
                    logger.info(f"Chờ {wait_time} giây để thử lại...")
                    time.sleep(wait_time)
                    # Tính lại kích thước file để chuẩn bị resume
                    file_size = filepath.stat().st_size if filepath.exists() else 0
                    headers = {'Range': f'bytes={file_size}-'} if file_size > 0 else {}

        return False


if __name__ == "__main__":
    pass