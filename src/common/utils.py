#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import requests
import re
import os
import sys
import hashlib
import base64
import time
import src
import logging

logger = logging.getLogger(__name__)

class Utils(object):
    def __init__(self):
        pass

    def replaceStr(self, filenamestr: str):
        """
        Replace illegal characters and shorten the length so it can be used as a filename.
        """
        # Match Chinese characters, letters, numbers, and spaces
        match = "([0-9A-Za-z\u4e00-\u9fa5]+)"

        result = re.findall(match, filenamestr)

        result = "".join(result).strip()
        if len(result) > 20:
            result = result[:20]
        # Remove leading and trailing spaces
        return result

    def resource_path(self, relative_path):
        # Check if running in a bundled executable (e.g. PyInstaller)
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def str2bool(self, v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            return True

    def generate_random_str(self, length=16):
        """Tạo chuỗi ngẫu nhiên"""
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789='
        return ''.join(random.choice(chars) for _ in range(length))

    # Reference: https://www.52pojie.cn/thread-1589242-1-1.html
    def getttwid(self):
        url = 'https://ttwid.bytedance.com/ttwid/union/register/'
        data = '{"region":"cn","aid":1768,"needFid":false,"service":"www.ixigua.com","migrate_info":{"ticket":"","source":"node"},"cbUrlProtocol":"https","union":true}'
        try:
            res = requests.post(url=url, data=data, timeout=10)
            for name, value in res.cookies.items():
                if name == 'ttwid':
                    return value
        except Exception as e:
            logger.warning(f"Không thể lấy ttwid: {e}")
            return None

    def getXbogus(self, payload, form='', ua=src.ua):
        xbogus = self.get_xbogus(payload, ua, form)
        params = payload + "&X-Bogus=" + xbogus
        return params

    def get_xbogus(self, payload, ua, form):
        short_str = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe="
        arr2 = self.get_arr2(payload, ua, form)

        garbled_string = self.get_garbled_string(arr2)

        xbogus = ""

        for i in range(0, 21, 3):
            char_code_num0 = garbled_string[i]
            char_code_num1 = garbled_string[i + 1]
            char_code_num2 = garbled_string[i + 2]
            base_num = char_code_num2 | char_code_num1 << 8 | char_code_num0 << 16
            str1 = short_str[(base_num & 16515072) >> 18]
            str2 = short_str[(base_num & 258048) >> 12]
            str3 = short_str[(base_num & 4032) >> 6]
            str4 = short_str[base_num & 63]
            xbogus += str1 + str2 + str3 + str4

        return xbogus

    def get_garbled_string(self, arr2):
        # Rearrange elements of arr2 into a specific pattern
        p = [
            arr2[0], arr2[10], arr2[1], arr2[11], arr2[2], arr2[12], arr2[3], arr2[13], arr2[4], arr2[14],
            arr2[5], arr2[15], arr2[6], arr2[16], arr2[7], arr2[17], arr2[8], arr2[18], arr2[9]
        ]

        char_array = [chr(i) for i in p]
        f = []
        f.extend([2, 255])
        tmp = ['ÿ']
        bytes_ = self._0x30492c(tmp, "".join(char_array))

        for i in range(len(bytes_)):
            f.append(bytes_[i])

        return f

    def get_arr2(self, payload, ua, form):
        # Create salt arrays from MD5 hashes of input
        salt_payload_bytes = hashlib.md5(hashlib.md5(payload.encode()).digest()).digest()
        salt_payload = [byte for byte in salt_payload_bytes]

        salt_form_bytes = hashlib.md5(hashlib.md5(form.encode()).digest()).digest()
        salt_form = [byte for byte in salt_form_bytes]

        ua_key = ['\u0000', '\u0001', '\u000e']
        salt_ua_bytes = hashlib.md5(base64.b64encode(self._0x30492c(ua_key, ua))).digest()
        salt_ua = [byte for byte in salt_ua_bytes]

        timestamp = int(time.time())
        canvas = 1489154074

        arr1 = [
            64,  # fixed value
            0,   # fixed value
            1,   # fixed value
            14,  # fixed value (note: 14, 12, 0 have appeared)
            salt_payload[14],  # related to payload
            salt_payload[15],
            salt_form[14],     # related to form
            salt_form[15],
            salt_ua[14],       # related to ua
            salt_ua[15],
            (timestamp >> 24) & 255,
            (timestamp >> 16) & 255,
            (timestamp >> 8) & 255,
            (timestamp >> 0) & 255,
            (canvas >> 24) & 255,
            (canvas >> 16) & 255,
            (canvas >> 8) & 255,
            (canvas >> 0) & 255,
            64,  # checksum
        ]

        # XOR all elements except first and last to calculate checksum
        for i in range(1, len(arr1) - 1):
            arr1[18] ^= arr1[i]

        # Rearrange arr1 into arr2
        arr2 = [arr1[0], arr1[2], arr1[4], arr1[6], arr1[8], arr1[10], arr1[12], arr1[14], arr1[16], arr1[18], arr1[1],
                arr1[3], arr1[5], arr1[7], arr1[9], arr1[11], arr1[13], arr1[15], arr1[17]]

        return arr2

    def _0x30492c(self, a, b):
        # Custom encryption function (RC4-like algorithm)
        d = [i for i in range(256)]
        c = 0
        result = bytearray(len(b))

        # Key-scheduling algorithm
        for i in range(256):
            c = (c + d[i] + ord(a[i % len(a)])) % 256
            e = d[i]
            d[i] = d[c]
            d[c] = e

        t = 0
        c = 0

        # Pseudo-random generation algorithm
        for i in range(len(b)):
            t = (t + 1) % 256
            c = (c + d[t]) % 256
            e = d[t]
            d[t] = d[c]
            d[c] = e
            result[i] = ord(b[i]) ^ d[(d[t] + d[c]) % 256]

        return result


if __name__ == "__main__":
    pass
