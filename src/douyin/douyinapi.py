#!/usr/bin/env python
# -*- coding: utf-8 -*-


import re
import random
from urllib.parse import quote, urlencode
from datetime import datetime

import requests
import json
import time
import copy
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.common.abogus import ABogus
from src.douyin import douyin_headers
from src.douyin.database import Database
from src.douyin.urls import Urls
from src.douyin.result import Result
from src.common import utils
import logging

logger = logging.getLogger(__name__)

class DouyinApi(object):

    # Common browser/device params shared across all API calls
    _COMMON_PARAMS = (
        'device_platform=webapp&aid=6383&channel=channel_pc_web'
        '&pc_client_type=1&version_code=170400&version_name=17.4.0'
        '&cookie_enabled=true&screen_width=1920&screen_height=1080'
        '&browser_language=zh-CN&browser_platform=MacIntel'
        '&browser_name=Chrome&browser_version=122.0.0.0'
        '&browser_online=true&engine_name=Blink&engine_version=122.0.0.0'
        '&os_name=Mac&os_version=10.15.7&cpu_core_num=8&device_memory=8'
        '&platform=PC&downlink=10&effective_type=4g&round_trip_time=50'
    )
    def __init__(self, database_path: str | None = "data.db", cookie: str | None = None):
        self.urls = Urls()
        self.result = Result()
        self.timeout = 60
        self.max_consecutive_errors = 3
        self.database = Database(database_path) if database_path else None
        self.cookie = cookie

        self.session = requests.Session()
        retries = Retry(
            total=5,  # Number of retries
            backoff_factor=0.3,  # Backoff factor between attempts (0.3, 0.6, 1.2s...)
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Apply cookie from config to session headers
        if cookie:
            self.session.headers.update({'Cookie': cookie})
            douyin_headers["Cookie"] = cookie
            orig_prepare_request = self.session.prepare_request

            def _custom_prepare_request(request):
                prep = orig_prepare_request(request)
                if self.cookie:
                    prep.headers['Cookie'] = self.cookie
                return prep

            self.session.prepare_request = _custom_prepare_request

    def _get_headers(self) -> dict:
        headers = copy.deepcopy(douyin_headers)
        active_cookie = getattr(self, "cookie", None) or douyin_headers.get("Cookie")
        if active_cookie:
            headers["Cookie"] = active_cookie
        return headers

    # Extract URL from share link or raw clipboard text
    def getShareLink(self, string):
        if not string or not str(string).strip():
            raise IndexError("Input text is empty")

        punctuation_strip = '),.!?，。！？;；:：\'"【】（）《》、~ \t\r\n'

        # 1. Prioritize Douyin ecosystem URLs (v.douyin.com, douyin.com, iesdouyin.com)
        douyin_match = re.search(
            r'(?:https?://)?(?:[a-zA-Z0-9\-]+\.)?(?:douyin\.com|iesdouyin\.com)/[a-zA-Z0-9_./\-?&=%#+:@!~*]*',
            string,
            re.IGNORECASE,
        )
        if douyin_match:
            url = douyin_match.group(0).rstrip(punctuation_strip)
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return url

        # 2. Fallback to generic http/https URL
        generic_match = re.search(
            r'https?://[a-zA-Z0-9_./\-?&=%#+:@!~*]+',
            string,
            re.IGNORECASE,
        )
        if generic_match:
            return generic_match.group(0).rstrip(punctuation_strip)

        raise IndexError(f"No valid Douyin or HTTP URL found in text: {string}")

    # Get aweme_id or sec_uid from URL
    # Supports both https://www.iesdouyin.com and https://v.douyin.com
    def getKey(self, url):
        key = None
        key_type = None

        try:
            r = self.session.get(url=url, headers=self._get_headers())
        except Exception as e:
            logger.error(f"Error in getKey: {str(e)}")
            logger.error('Invalid link!')
            return key_type, key

        urlstr = str(r.request.path_url)

        if "/user/" in urlstr:
            # Get sec_uid
            key = re.findall(r'user/([\d\D]*?)(?:\?|$)', urlstr)[0]
            key_type = "user"
        elif "/video/" in urlstr:
            # Get aweme_id
            key = re.findall(r'video/(\d+)?', urlstr)[0]
            key_type = "aweme"
        elif "/note/" in urlstr:
            key = re.findall(r'note/(\d+)?', urlstr)[0]
            key_type = "aweme"
        elif "/mix/detail/" in urlstr:
            key = re.findall(r'/mix/detail/(\d+)?', urlstr)[0]
            key_type = "mix"
        elif "/collection/" in urlstr:
            key = re.findall(r'/collection/(\d+)?', urlstr)[0]
            key_type = "mix"
        elif "/music/" in urlstr:
            key = re.findall(r'music/(\d+)?', urlstr)[0]
            key_type = "music"
        elif "/webcast/reflow/" in urlstr:
            key1 = re.findall(r'reflow/(\d+)?', urlstr)[0]
            url = self.urls.LIVE2 + utils.getXbogus(f'live_id=1&room_id={key1}&app_id=1128')
            res = self.session.get(url, headers=self._get_headers())
            resjson = json.loads(res.text)
            key = resjson['data']['room']['owner']['web_rid']
            key_type = "live"
        elif "live.douyin.com" in r.url:
            key = r.url.replace('https://live.douyin.com/', '')
            key_type = "live"

        if key is None or key_type is None:
            logger.error('Invalid link! Could not extract ID')
            return key_type, key

        return key_type, key

    def getAwemeInfoApi(self, aweme_id):
        if aweme_id is None:
            return None
        start = time.time()
        while True:
            try:
                detail_params = {
                    "aweme_id": aweme_id,
                    "device_platform": "webapp",
                    "aid": "6383",
                    "channel": "channel_pc_web",
                    "pc_client_type": 1,
                    "version_code": "290100",
                    "version_name": "29.1.0",
                    "cookie_enabled": "true",
                    "screen_width": 1920,
                    "screen_height": 1080,
                    "browser_language": "zh-CN",
                    "browser_platform": "Win32",
                    "browser_name": "Chrome",
                    "browser_version": "130.0.0.0",
                    "browser_online": "true",
                    "engine_name": "Blink",
                    "engine_version": "130.0.0.0",
                    "os_name": "Windows",
                    "os_version": "10",
                    "cpu_core_num": 12,
                    "device_memory": 8,
                    "platform": "PC",
                    "downlink": "1.35",
                    "effective_type": "4g",
                    "from_user_page": "1",
                    "locate_query": "false",
                    "need_time_list": "1",
                    "pc_libra_divert": "Windows",
                    "publish_video_strategy_type": "2",
                    "round_trip_time": "0",
                    "show_live_replay_strategy": "1",
                    "time_list_query": "0",
                    "whale_cut_token": "",
                    "uifid": "",
                    "update_version_code": "170400",
                    "msToken": ""
                }

                a_bogus = ABogus().get_value(detail_params)

                jx_url = self.urls.POST_DETAIL + f"{urlencode(detail_params)}&a_bogus={quote(a_bogus, safe='')}"

                headers = self._get_headers()
                response = self.session.get(url=jx_url, headers=headers, timeout=10)

                if response.status_code in (403, 429) or "ArgusSecurity" in response.text:
                    logger.warning(
                        f"Douyin WAF risk control triggered (HTTP {response.status_code}: {response.text[:80].strip()}), backing off..."
                    )
                    time.sleep(2 + random.uniform(1.0, 2.5))
                    if time.time() - start > self.timeout:
                        raise RuntimeError(f"Douyin WAF risk control triggered (HTTP {response.status_code}: {response.text[:80].strip()})")
                    continue

                if len(response.text) == 0:
                    logger.warning("Single API Video returned an empty response, retrying...")
                    time.sleep(1 + random.uniform(0.5, 1.5))
                    if time.time() - start > self.timeout:
                        return None
                    continue

                datadict = json.loads(response.text)
                if datadict is not None and datadict.get("status_code") == 0:
                    break
                else:
                    logger.warning(f"Single API Video returned non-zero status: {datadict.get('status_code') if datadict else 'None'}")
                    time.sleep(1 + random.uniform(0.5, 1.5))
                    if time.time() - start > self.timeout:
                        return None
                    continue
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"Error in getAwemeInfoApi: {str(e)} | status={getattr(response, 'status_code', None)} | text_len={len(getattr(response, 'text', ''))} | sample={repr(getattr(response, 'text', '')[:200])}")
                end = time.time()
                if end - start > self.timeout:
                    return None
                # Delay before retry to avoid API spam
                time.sleep(1 + random.uniform(0, 1))

        # Clear existing data in self.awemeDict
        self.result.clearDict(self.result.awemeDict)

        # Default type is video
        awemeType = 0
        try:
            if datadict['aweme_detail']["images"] is not None:
                awemeType = 1
        except Exception:
            logger.warning("No 'images' field found in the API response")

        # Convert the data into custom format
        self.result.dataConvert(awemeType, self.result.awemeDict, datadict['aweme_detail'])

        #Save
        aweme_data = copy.deepcopy(self.result.awemeDict)
        if self.database and aweme_data:
            self.database.upsert_aweme(aweme_data, is_user_post=True)

        return self.result.awemeDict

    def getUserDetailApi(self, sec_uid):
        """Fetch creator detailed profile info including aweme_count."""
        if not sec_uid:
            return None
        try:
            detail_params = f"sec_user_id={sec_uid}&publish_video_strategy_type=2&personal_center_strategy=1&{self._COMMON_PARAMS}"
            # 1. Try modern a_bogus endpoint token
            try:
                a_bogus = ABogus().get_value(detail_params)
                url = self.urls.USER_DETAIL + f"{detail_params}&a_bogus={quote(a_bogus, safe='')}"
                res = self.session.get(url=url, headers=self._get_headers(), timeout=self.timeout)
                if res.status_code == 200 and len(res.text) > 0:
                    datadict = json.loads(res.text)
                    if datadict and datadict.get("status_code") == 0:
                        user_data = datadict.get("user") or {}
                        if user_data:
                            self.result.clearDict(self.result.authorDict)
                            self.result.dataConvert(0, self.result.authorDict, user_data)
                            return copy.deepcopy(self.result.authorDict)
            except Exception as e:
                logger.debug(f"getUserDetailApi with a_bogus failed, falling back: {e}")

            # 2. Fallback to X-Bogus signature
            url = self.urls.USER_DETAIL + utils.getXbogus(detail_params)
            res = self.session.get(url=url, headers=self._get_headers(), timeout=self.timeout)
            if res.status_code == 200 and len(res.text) > 0:
                datadict = json.loads(res.text)
                if datadict and datadict.get("status_code") == 0:
                    user_data = datadict.get("user") or {}
                    if user_data:
                        self.result.clearDict(self.result.authorDict)
                        self.result.dataConvert(0, self.result.authorDict, user_data)
                        return copy.deepcopy(self.result.authorDict)
        except Exception as e:
            logger.error(f"Error in getUserDetailApi: {str(e)}")
        return None

    def getUserInfoApi(self, sec_uid, mode="post", count=18, number=0, increase=False, start_time="", end_time=""):
        if sec_uid is None:
            return None

        start_time = start_time or "1970-01-01"
        end_time = end_time or datetime.now().strftime("%Y-%m-%d")

        max_cursor = 0
        awemeList = []
        total_fetched = 0
        consecutive_errors = 0

        while True:
            try:
                detail_params = f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&{self._COMMON_PARAMS}'

                if mode == "post":
                    url = self.urls.USER_POST + utils.getXbogus(detail_params)
                elif mode == "like":
                    try:
                        url = self.urls.USER_FAVORITE_A + utils.getXbogus(detail_params)
                    except:
                        url = self.urls.USER_FAVORITE_B + utils.getXbogus(detail_params)
                else:
                    return None

                res = self.session.get(url=url, headers=self._get_headers(), timeout=self.timeout)
                if len(res.text) == 0:
                    consecutive_errors += 1
                    logger.warning(f"User Get Post/Favorite API return an empty response (error {consecutive_errors}/{self.max_consecutive_errors})")
                    if consecutive_errors >= self.max_consecutive_errors:
                        logger.error("Max consecutive errors reached, stopping.")
                        break
                    time.sleep(2 + random.uniform(0, 1))
                    continue

                datadict = json.loads(res.text)

                if datadict is None or datadict["status_code"] != 0:
                    consecutive_errors += 1
                    logger.warning(f"API returned error status: {datadict.get('status_code') if datadict else 'None'} (error {consecutive_errors}/{self.max_consecutive_errors})")
                    if consecutive_errors >= self.max_consecutive_errors:
                        logger.error("Max consecutive errors reached, stopping.")
                        break
                    time.sleep(2 + random.uniform(0, 1))
                    continue

                if "aweme_list" not in datadict:
                    logger.warning("No aweme_list in API response")
                    break

                # Reset consecutive error counter on success
                consecutive_errors = 0

                current_count = len(datadict["aweme_list"])
                total_fetched += current_count
                logger.info(f"Fetched: {total_fetched} items (+{current_count})")

                # Process aweme_list
                for aweme in datadict["aweme_list"]:
                    create_time = time.strftime("%Y-%m-%d", time.localtime(int(aweme.get("create_time", 0))))

                    if not (start_time <= create_time <= end_time):
                        continue

                    if number > 0 and len(awemeList) >= number:
                        logger.info(f"Reached required number: {number}")
                        return awemeList

                    self.result.clearDict(self.result.awemeDict)
                    aweme_type = 1 if aweme.get("images") else 0
                    self.result.dataConvert(aweme_type, self.result.awemeDict, aweme)
                    aweme_data = copy.deepcopy(self.result.awemeDict)
                    if aweme_data:
                        awemeList.append(aweme_data)

                        if increase and self.database and aweme.get("is_top", 0)==0:
                            _awid = str(aweme.get("aweme_id"))
                            if mode == "post" and self.database.has_user_post(sec_uid, _awid):
                                logger.info("Incremental update completed")
                                return awemeList

                            elif mode == "like" and self.database.has_user_like(sec_uid, _awid):
                                logger.info("Incremental update completed")
                                return awemeList

                if not datadict.get("has_more", 0):
                    logger.info(f"No more data available")
                    break

                max_cursor = datadict["max_cursor"]

                # Delay between pagination requests to avoid rate limiting
                time.sleep(1 + random.uniform(0, 1))

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in getUserInfoApi: {str(e)} (error {consecutive_errors}/{self.max_consecutive_errors})")
                if consecutive_errors >= self.max_consecutive_errors:
                    logger.error("Max consecutive errors reached, stopping.")
                    break
                time.sleep(1 + random.uniform(0, 1))
                continue

        if self.database and awemeList:
            if mode=="post":
                self.database.bulk_upsert_awemes(awemeList, is_user_posts=True)

            elif mode=="like":
                self.database.bulk_upsert_awemes(awemeList, is_user_posts=False, as_likes_for=sec_uid)

        return awemeList

    def getLiveInfoApi(self, web_rid: str):
        start = time.time()
        while True:
            try:
                detail_params = (
                    f'aid=6383&device_platform=web&web_rid={web_rid}&channel=channel_pc_web&pc_client_type=1'
                    f'&version_code=170400&version_name=17.4.0&cookie_enabled=true&screen_width=1920'
                    f'&screen_height=1080&browser_language=zh-CN&browser_platform=MacIntel&browser_name=Chrome'
                    f'&browser_version=122.0.0.0&browser_online=true&engine_name=Blink&engine_version=122.0.0.0'
                    f'&os_name=Mac&os_version=10.15.7&cpu_core_num=8&device_memory=8&platform=PC'
                    f'&downlink=10&effective_type=4g&round_trip_time=50'
                )
                live_api = self.urls.LIVE + utils.getXbogus(detail_params)

                response = self.session.get(live_api, headers=self._get_headers(), timeout=10)
                if len(response.text)==0:
                    logger.warning("Livestream API return an empty response")
                    return {}

                live_json = json.loads(response.text)
                if live_json is not None and live_json['status_code'] == 0:
                    break

            except Exception as e:
                logger.error(f"Error in getLiveApi: {str(e)}")
                end = time.time()
                if end - start > self.timeout:
                    return None

        self.result.clearDict(self.result.liveDict)

        self.result.liveDict["awemeType"] = "2"

        self.result.liveDict["status"] = live_json['data']['data'][0]['status_str']

        if self.result.liveDict["status"] == "4":
            logger.info("Stream ended!")
            return self.result.liveDict, live_json

        self.result.liveDict["title"] = live_json['data']['data'][0]['title']

        self.result.liveDict["cover"] = live_json['data']['data'][0]['cover']['url_list'][0]

        self.result.liveDict["avatar"] = live_json['data']['data'][0]['owner']['avatar_thumb']['url_list'][0].replace(
            "100x100", "1080x1080")

        self.result.liveDict["user_count"] = live_json['data']['data'][0]['user_count_str']

        self.result.liveDict["nickname"] = live_json['data']['data'][0]['owner']['nickname']

        self.result.liveDict["sec_uid"] = live_json['data']['data'][0]['owner']['sec_uid']

        self.result.liveDict["display_long"] = live_json['data']['data'][0]['room_view_stats']['display_long']

        stream_url_obj = live_json['data']['data'][0].get('stream_url') or {}
        flv_pull = stream_url_obj.get('flv_pull_url') or {}
        self.result.liveDict["flv_pull_url"] = flv_pull.get("FULL_HD1", "")

        try:
            self.result.liveDict["partition"] = live_json['data']['partition_road_map']['partition']['title']
            self.result.liveDict["sub_partition"] = \
                live_json['data']['partition_road_map']['sub_partition']['partition']['title']
        except Exception:
            self.result.liveDict["partition"] = 'None'
            self.result.liveDict["sub_partition"] = 'None'

        return self.result.liveDict, live_json

    def getMixInfoApi(self, mix_id: str, count=35, number=0, start_time="", end_time=""):
        if mix_id is None:
            return None

        if not start_time:
            start_time = "1970-01-01"
        if not end_time:
            end_time = time.strftime("%Y-%m-%d")

        cursor = 0
        awemeList = []
        total_fetched = 0

        start = time.time()
        while True:
            try:
                mix_params = f'mix_id={mix_id}&cursor={cursor}&count={count}&{self._COMMON_PARAMS}'
                url = self.urls.USER_MIX + utils.getXbogus(mix_params)

                res = self.session.get(url=url, headers=self._get_headers(), timeout=10)

                if res.status_code != 200:
                    logger.warning(f"Mix API HTTP request failed: {res.status_code}")
                    break

                if len(res.text) == 0:
                    logger.warning("Mix API returned an empty response")
                    return awemeList

                datadict = json.loads(res.text)

                if datadict is None or datadict.get("status_code", -1) != 0:
                    logger.warning(f"Mix API returned error status: {datadict.get('status_code') if datadict else 'None'}")
                    break

                if "aweme_list" not in datadict or not datadict["aweme_list"]:
                    logger.warning("No aweme_list in Mix API response or empty list")
                    break

                current_count = len(datadict["aweme_list"])
                total_fetched += current_count
                logger.info(f"Fetched: {total_fetched} items from mix (+{current_count})")

                # Process aweme_list
                for aweme in datadict["aweme_list"]:
                    create_time = time.strftime(
                        "%Y-%m-%d",
                        time.localtime(int(aweme.get("create_time", 0)))
                    )

                    if not (start_time <= create_time <= end_time):
                        continue

                    if number > 0 and len(awemeList) >= number:
                        logger.info(f"Reached required number: {number}")
                        return awemeList

                    self.result.clearDict(self.result.awemeDict)
                    aweme_type = 1 if aweme.get("images") else 0
                    self.result.dataConvert(aweme_type, self.result.awemeDict, aweme)
                    aweme_data = copy.deepcopy(self.result.awemeDict)
                    if aweme_data:
                        awemeList.append(aweme_data)

                if not datadict.get("has_more", False):
                    logger.info("No more mix data available")
                    break

                cursor = datadict["cursor"]

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in getMixInfoApi: {str(e)}")
                break
            except Exception as e:
                logger.error(f"Error in getMixInfoApi: {str(e)}")
                end = time.time()
                if end - start > self.timeout:
                    logger.warning("Timeout reached in getMusicInfo")
                    break
                continue

        if self.database and awemeList:
            self.database.bulk_upsert_awemes(awemeList, is_user_posts=False)

        return awemeList

    def getUserAllMixInfoApi(self, sec_uid: str, count=35, start_time="", end_time=""):
        if sec_uid is None:
            return None

        if not start_time:
            start_time = "1970-01-01"
        if not end_time:
            end_time = time.strftime("%Y-%m-%d")

        cursor = 0
        mixDict = {}

        start = time.time()
        while True:
            try:
                mix_list_params = f'sec_user_id={sec_uid}&count={count}&cursor={cursor}&{self._COMMON_PARAMS}'
                url = self.urls.USER_MIX_LIST + utils.getXbogus(mix_list_params)

                res = self.session.get(url=url, headers=self._get_headers(), timeout=10)

                if res.status_code != 200:
                    logger.warning(f"Mix List API HTTP request failed: {res.status_code}")
                    break

                if len(res.text) == 0:
                    logger.warning("Mix API returned an empty response")
                    return mixDict

                try:
                    datadict = json.loads(res.text)
                except json.JSONDecodeError:
                    raise

                if datadict is None or datadict.get("status_code", -1) != 0:
                    logger.warning(f"API returned error status: {datadict.get('status_code') if datadict else 'None'}")
                    break

                if "mix_infos" not in datadict or not datadict["mix_infos"]:
                    logger.warning("No mix_infos in API response")
                    break

                for mix in datadict["mix_infos"]:
                    create_time = time.strftime("%Y-%m-%d", time.localtime(int(mix.get("create_time", 0))))

                    if not (start_time <= create_time <= end_time):
                        continue

                    mixDict[mix["mix_id"]] = mix["mix_name"]

                if not datadict.get("has_more", 0):
                    logger.info(f"No more data available")
                    break


                cursor = datadict["cursor"]

            except Exception as e:
                logger.error(f"Error in getUserInfoApi: {str(e)}")
                end = time.time()
                if end - start > self.timeout:
                    logger.warning("Timeout reached")
                    break

                continue

        return mixDict

    def getMusicInfo(self, music_id: str, count=35, number=0, start_time="", end_time=""):
        if music_id is None:
            return None

        if not start_time:
            start_time = "1970-01-01"
        if not end_time:
            end_time = time.strftime("%Y-%m-%d")

        cursor = 0
        total_fetched = 0
        awemeList = []

        start = time.time()  # Start time
        while True:
            try:
                music_params = f'music_id={music_id}&cursor={cursor}&count={count}&{self._COMMON_PARAMS}'
                url = self.urls.MUSIC + utils.getXbogus(music_params)

                res = self.session.get(url=url, headers=self._get_headers(), timeout=10)

                if res.status_code != 200:
                    logger.warning(f"Music API HTTP request failed: {res.status_code}")
                    break

                if len(res.text) == 0:
                    logger.warning("Music API returned an empty response")
                    return awemeList

                datadict = json.loads(res.text)

                if datadict is None or datadict.get("status_code", -1) != 0:
                    logger.warning(f"Music API returned error status: {datadict.get('status_code') if datadict else 'None'}")
                    break

                if "aweme_list" not in datadict or not datadict["aweme_list"]:
                    logger.warning("No aweme_list in Music API response or empty list")
                    break

                current_count = len(datadict["aweme_list"])
                total_fetched += current_count
                logger.info(f"Fetched: {total_fetched} items (+{current_count})")

                for aweme in datadict["aweme_list"]:

                    create_time = time.strftime("%Y-%m-%d",time.localtime(int(aweme.get("create_time", 0))))

                    if not (start_time <= create_time <= end_time):
                        continue

                    if number > 0 and len(awemeList) >= number:
                        logger.info(f"Reached required number: {number}")

                        return awemeList

                    self.result.clearDict(self.result.awemeDict)
                    aweme_type = 1 if aweme.get("images") else 0
                    self.result.dataConvert(aweme_type, self.result.awemeDict, aweme)
                    aweme_data = copy.deepcopy(self.result.awemeDict)
                    if aweme_data:
                        awemeList.append(aweme_data)

                if not datadict.get("has_more", 0):
                    logger.info("No more data available")
                    break

                cursor = datadict["cursor"]

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in getMixInfoApi: {str(e)}")
                break

            except Exception as e:
                logger.error(f"Error in getMusicInfo: {str(e)}")
                end = time.time()
                if end - start > self.timeout:
                    logger.warning("Timeout reached in getMusicInfo")
                    break

                continue

        if self.database and awemeList:
            self.database.bulk_upsert_awemes(awemeList, is_user_posts=False)

        return awemeList

if __name__ == "__main__":
    pass