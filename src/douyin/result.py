#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import copy
import logging

logger = logging.getLogger(__name__)


class Result(object):
    def __init__(self):
        # Author information
        self.authorDict = {
            "avatar_thumb": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "avatar": { # Large Avatar
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            # Number of works / published posts
            "aweme_count": 0,
            "cover_url": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            # Number of liked posts
            "favoriting_count": "",
            # Number of followers
            "follower_count": "",
            # Number of followings
            "following_count": "",
            # Nickname
            "nickname": "",
            "prevent_download": "",
            # User's sec_uid
            "sec_uid": "",
            # Whether account is private
            "secret": "",
            # Short ID
            "short_id": "",
            # Signature/bio
            "signature": "",
            # Total likes received
            "total_favorited": "",
            # User ID
            "uid": "",
            # Custom unique ID (Douyin handle)
            "unique_id": "",
            # Age
            "user_age": "",
        }

        # Music information
        self.musicDict = {
            "cover_hd": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_large": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_medium": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover_thumb": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            # Music author's Douyin handle
            "owner_handle": "",
            # Music author's ID
            "owner_id": "",
            # Music author's nickname
            "owner_nickname": "",
            "play_url": {
                "height": "",
                "uri": "",
                "url_key": "",
                "url_list": [],
                "width": ""
            },
            # Music title
            "title": "",
        }

        # Video information
        self.videoDict = {
            "play_addr": {
                "uri": "",
                "url_list": [],
            },
            "cover_original_scale": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "dynamic_cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "origin_cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            },
            "cover": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": ""
            }
        }

        # Collection (Mix) information
        self.mixInfo = {
            "cover_url": {
                "height": "",
                "uri": "",
                "url_list": [],
                "width": 720
            },
            "ids": "",
            "is_serial_mix": "",
            "mix_id": "",
            "mix_name": "",
            "mix_pic_type": "",
            "mix_type": "",
            "statis": {
                "current_episode": "",
                "updated_to_episode": ""
            }
        }

        # Post information — use deepcopy to avoid shared mutable references
        self.awemeDict = {
            # Post creation time
            "create_time": "",
            # awemeType=0 video, awemeType=1 image album, awemeType=2 live stream
            "awemeType": "",
            # Post ID
            "aweme_id": "",
            # Author information — deep copy to avoid shared state
            "author": copy.deepcopy(self.authorDict),
            # Description
            "desc": "",
            # Images
            "images": [],
            # Music — deep copy
            "music": copy.deepcopy(self.musicDict),
            # Collection info — deep copy
            "mix_info": copy.deepcopy(self.mixInfo),
            # Video — deep copy
            "video": copy.deepcopy(self.videoDict),
            # Statistics
            "statistics": {
                "admire_count": "",
                "collect_count": "",
                "comment_count": "",
                "digg_count": "",
                "play_count": "",
                "share_count": ""
            }
        }

        # User's list of posts
        self.awemeList = []

        # Live stream information
        self.liveDict = {
            # awemeType=0 video, awemeType=1 image album, awemeType=2 live stream
            "awemeType": "",
            # Whether live streaming
            "status": "",
            # Live stream title
            "title": "",
            # Live cover image
            "cover": "",
            # Avatar
            "avatar": "",
            # Viewer count
            "user_count": "",
            # Nickname
            "nickname": "",
            # sec_uid
            "sec_uid": "",
            # Live stream display status
            "display_long": "",
            # Stream URL
            "flv_pull_url": "",
            # Category
            "partition": "",
            "sub_partition": "",
        }

    # Convert raw JSON data (dataRaw) into a simplified custom data format (dataNew)
    def dataConvert(self, awemeType, dataNew, dataRaw):
        for item in dataNew:
            try:
                # Convert creation time
                if item == "create_time":
                    dataNew['create_time'] = time.strftime(
                        "%Y-%m-%d %H.%M.%S", time.localtime(dataRaw['create_time']))
                    continue

                # Set awemeType
                if item == "awemeType":
                    dataNew["awemeType"] = awemeType
                    continue

                # If the parsed link is an image
                if item == "images":
                    if awemeType == 1:
                        for image in dataRaw[item]:
                            # Create a fresh dict for each image instead of mutating shared picDict
                            pic = {
                                "height": image.get("height", ""),
                                "mask_url_list": image.get("mask_url_list", ""),
                                "uri": image.get("uri", ""),
                                "url_list": copy.deepcopy(image.get("url_list", [])),
                                "width": image.get("width", ""),
                            }
                            # FIX: append to dataNew["images"] instead of self.awemeDict["images"]
                            dataNew["images"].append(pic)
                    continue

                # If the parsed link is a video
                if item == "video":
                    if awemeType == 0:
                        self.dataConvert(awemeType, dataNew[item], dataRaw[item])
                    continue

                # Enlarge small avatar
                if item == "avatar":
                    for i in dataNew[item]:
                        if i == "url_list":
                            for j in dataNew.get("avatar_thumb", {}).get("url_list", []):
                                dataNew[item][i].append(j.replace("100x100", "1080x1080"))
                        elif i == "uri":
                            dataNew[item][i] = dataNew.get("avatar_thumb", {}).get(i, "").replace("100x100", "1080x1080")
                        else:
                            dataNew[item][i] = dataNew.get("avatar_thumb", {}).get(i, "")
                    continue

                # Original JSON is [{}], we use {}
                if item == "cover_url":
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item][0])
                    continue

                # Get 1080p video from URI - prefer bit_rate, fallback to play_addr
                if item == "play_addr":
                    bit_rate = dataRaw.get("bit_rate") or []
                    if bit_rate:
                        play_addr_data = bit_rate[0].get("play_addr") or {}
                    else:
                        play_addr_data = dataRaw.get("play_addr") or {}
                    
                    dataNew[item]["uri"] = play_addr_data.get("uri", "")
                    dataNew[item]["url_list"] = copy.deepcopy(play_addr_data.get("url_list", []))
                    continue

                # Regular recursive dictionary traversal
                if isinstance(dataNew[item], dict):
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item])
                else:
                    # Assign value
                    dataNew[item] = dataRaw[item]
            except Exception as e:
                # Log the error for debugging instead of silently suppressing
                logger.debug(f"dataConvert skipped field '{item}': {e}")

    def clearDict(self, data):
        for item in data:
            # Recursive dictionary traversal
            if isinstance(data[item], dict):
                self.clearDict(data[item])
            elif isinstance(data[item], list):
                data[item] = []
            else:
                data[item] = ""


if __name__ == '__main__':
    pass
