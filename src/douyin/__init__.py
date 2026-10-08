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
    'sec-ch-ua': '"Chromium";v="130", "Not?A_Brand";v="99", "Google Chrome";v="130"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'Cookie': f"msToken={utils.generate_random_str(107)}; ttwid={utils.getttwid()};"
}