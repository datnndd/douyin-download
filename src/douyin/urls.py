#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Urls:
    """Douyin API endpoint URLs — class constants (no instance state needed)."""

    ######################################### WEB #########################################
    # Homepage Recommendations
    TAB_FEED = 'https://www.douyin.com/aweme/v1/web/tab/feed/?'

    # User Short Info (Returns as many user profiles as sec_uids provided)
    USER_SHORT_INFO = 'https://www.douyin.com/aweme/v1/web/im/user/info/?'

    # User Detailed Info
    USER_DETAIL = 'https://www.douyin.com/aweme/v1/web/user/profile/other/?'

    # User Posts
    USER_POST = 'https://www.douyin.com/aweme/v1/web/aweme/post/?'

    # Post Details
    POST_DETAIL = 'https://www.douyin.com/aweme/v1/web/aweme/detail/?'

    # User Favorites A
    # Requires odin_tt
    USER_FAVORITE_A = 'https://www.douyin.com/aweme/v1/web/aweme/favorite/?'

    # User Favorites B
    USER_FAVORITE_B = 'https://www.iesdouyin.com/web/api/v2/aweme/like/?'

    # User Watch History
    USER_HISTORY = 'https://www.douyin.com/aweme/v1/web/history/read/?'

    # User Collections
    USER_COLLECTION = 'https://www.douyin.com/aweme/v1/web/aweme/listcollection/?'

    # User Comments
    COMMENT = 'https://www.douyin.com/aweme/v1/web/comment/list/?'

    # Friends' Posts on Homepage
    FRIEND_FEED = 'https://www.douyin.com/aweme/v1/web/familiar/feed/?'

    # Followed Users' Posts
    FOLLOW_FEED = 'https://www.douyin.com/aweme/v1/web/follow/feed/?'

    # All Posts Under a Collection
    # Requires only X-Bogus
    USER_MIX = 'https://www.douyin.com/aweme/v1/web/mix/aweme/?'

    # All Collection Lists of a User
    # Requires ttwid
    USER_MIX_LIST = 'https://www.douyin.com/aweme/v1/web/mix/list/?'

    # Live Stream
    LIVE = 'https://live.douyin.com/webcast/room/web/enter/?'
    LIVE2 = 'https://webcast.amemv.com/webcast/room/reflow/info/?'

    # Music
    MUSIC = 'https://www.douyin.com/aweme/v1/web/music/aweme/?'

    #######################################################################################


if __name__ == '__main__':
    pass
