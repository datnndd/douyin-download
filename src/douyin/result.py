#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import copy


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
            "avatar": {  # Large avatar
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

        # Image information of Album
        self.picDict = {
            "height": "",
            "mask_url_list": "",
            "uri": "",
            "url_list": [],
            "width": ""
        }

        # Music information
        self.musicDict = {
            "cover_hd": {
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

        # Post information
        self.awemeDict = {
            # Post creation time
            "create_time": "",
            # awemeType=0 video, awemeType=1 image album, awemeType=2 live stream
            "awemeType": "",
            # Post ID
            "aweme_id": "",
            # Author information
            "author": self.authorDict,
            # Description
            "desc": "",
            # Images
            "images": [],
            # Music
            "music": self.musicDict,
            # Collection info
            "mix_info": self.mixInfo,
            # Video
            "video": self.videoDict,
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
                            for i in image:
                                self.picDict[i] = image[i]
                            # Deep copy dictionary
                            self.awemeDict["images"].append(copy.deepcopy(self.picDict))
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
                            for j in self.awemeDict["author"]["avatar_thumb"]["url_list"]:
                                dataNew[item][i].append(j.replace("100x100", "1080x1080"))
                        elif i == "uri":
                            dataNew[item][i] = self.awemeDict["author"]["avatar_thumb"][i].replace("100x100", "1080x1080")
                        else:
                            dataNew[item][i] = self.awemeDict["author"]["avatar_thumb"][i]
                    continue

                # Original JSON is [{}], we use {}
                if item == "cover_url":
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item][0])
                    continue

                # Get 1080p video from URI
                if item == "play_addr":
                    dataNew[item]["uri"] = dataRaw["bit_rate"][0]["play_addr"]["uri"]
                    # Alternative: use this API to get 1080p
                    # dataNew[item]["url_list"] = "https://aweme.snssdk.com/aweme/v1/play/?video_id=%s&ratio=1080p&line=0" \
                    #                             % dataNew[item]["uri"]
                    dataNew[item]["url_list"] = copy.deepcopy(dataRaw["bit_rate"][0]["play_addr"]["url_list"])
                    continue

                # Regular recursive dictionary traversal
                if isinstance(dataNew[item], dict):
                    self.dataConvert(awemeType, dataNew[item], dataRaw[item])
                else:
                    # Assign value
                    dataNew[item] = dataRaw[item]
            except Exception:
                # Suppress this warning to avoid confusion
                pass

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
