from src.douyin.douyinapi import DouyinApi

# Khởi tạo API (có thể truyền None để không dùng database)
api = DouyinApi(database_path=None)

# # 1. Test getShareLink
# share_text = " a a   a  a https://v.douyin.com/4hZpjnndDGM/"
# print("ShareLink:", api.getShareLink(share_text))
#
# # 2. Test getKey
# url = "https://v.douyin.com/4hZpjnndDGM/"
# print("Key:", api.getKey(url))
#
# # 3. Test getAwemeInfoApi (cần 1 aweme_id hợp lệ)
# aweme_id = "7538364728985341203"
# print("Aweme Info:", api.getAwemeInfoApi(aweme_id))
#
# # 4. Test getUserInfoApi (cần sec_uid hợp lệ)
sec_uid = "MS4wLjABAAAAm_kLk3csLErzzbZtjBpWy7hs6Wuy1_xWeuzmddGs9kI"
# print("User Posts:", api.getUserInfoApi(sec_uid, mode="post", number=10, count=35))
# print("User Likes:", api.getUserInfoApi(sec_uid, mode="like", number=10, count=35))
#
# # 5. Test getLiveInfoApi (cần web_rid hợp lệ)
# web_rid = "278888496353"
# print("Live Info:", api.getLiveInfoApi(web_rid))
#
# # 6. Test getMixInfoApi (cần mix_id hợp lệ)
# mix_id = "7462702389667645475"
# print("Mix Info:", api.getMixInfoApi(mix_id, number=3))
#
# # 7. Test getUserAllMixInfoApi
# print("All Mix:", api.getUserAllMixInfoApi(sec_uid))

# 8. Test getMusicInfo
# music_id = "7537625417147108138"
# print("Music Info:", api.getMusicInfo(music_id, number=1))

print(api.getUserInfoApi(sec_uid= sec_uid, mode="post", number=1, count=35))
