#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Urls(object):
    def __init__(self):
        ######################################### WEB #########################################
        # Homepage Recommendations
        self.TAB_FEED = 'https://www.douyin.com/aweme/v1/web/tab/feed/?'

        # User Short Info (Returns as many user profiles as sec_uids provided)
        self.USER_SHORT_INFO = 'https://www.douyin.com/aweme/v1/web/im/user/info/?'

        # User Detailed Info
        self.USER_DETAIL = 'https://www.douyin.com/aweme/v1/web/user/profile/other/?'

        # User Posts
        self.USER_POST = 'https://www.douyin.com/aweme/v1/web/aweme/post/?'

        # Post Details
        self.POST_DETAIL = 'https://www.douyin.com/aweme/v1/web/aweme/detail/?'

        # User Favorites A
        # Requires odin_tt
        self.USER_FAVORITE_A = 'https://www.douyin.com/aweme/v1/web/aweme/favorite/?'

        # User Favorites B
        self.USER_FAVORITE_B = 'https://www.iesdouyin.com/web/api/v2/aweme/like/?'

        # User Watch History
        self.USER_HISTORY = 'https://www.douyin.com/aweme/v1/web/history/read/?'

        # User Collections
        self.USER_COLLECTION = 'https://www.douyin.com/aweme/v1/web/aweme/listcollection/?'

        # User Comments
        self.COMMENT = 'https://www.douyin.com/aweme/v1/web/comment/list/?'

        # Friends’ Posts on Homepage
        self.FRIEND_FEED = 'https://www.douyin.com/aweme/v1/web/familiar/feed/?'

        # Followed Users’ Posts
        self.FOLLOW_FEED = 'https://www.douyin.com/aweme/v1/web/follow/feed/?'

        # All Posts Under a Collection
        # Requires only X-Bogus
        self.USER_MIX = 'https://www.douyin.com/aweme/v1/web/mix/aweme/?'

        # All Collection Lists of a User
        # Requires ttwid
        self.USER_MIX_LIST = 'https://www.douyin.com/aweme/v1/web/mix/list/?'

        # Live Stream
        self.LIVE = 'https://live.douyin.com/webcast/room/web/enter/?'
        self.LIVE2 = 'https://webcast.amemv.com/webcast/room/reflow/info/?'

        # Music
        self.MUSIC = 'https://www.douyin.com/aweme/v1/web/music/aweme/?'

        #######################################################################################


if __name__ == '__main__':
    pass
