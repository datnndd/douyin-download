#!/usr/bin/env python
# -*- coding: utf-8 -*-

import src
from src.common import utils

douyin_headers = {
    'User-Agent': src.ua,
    'referer': 'https://www.douyin.com/',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'accept-encoding': 'gzip, deflate, br',
    'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'Cookie': f"msToken={utils.generate_random_str(107)}; ttwid={utils.getttwid()}; odin_tt=324fb4ea4a89c0c05827e18a1ed9cf9bf8a17f7705fcc793fec935b637867e2a5a9b8168c885554d029919117a18ba69; passport_csrf_token=f61602fc63757ae0e4fd9d6bdcee4810;"
}