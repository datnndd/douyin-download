// Optimized Douyin.js based on abogus.py logic
// All content for learning and communication use only

class ABogus {
    constructor(platform = null) {
        // Constants from Python version
        this.__arguments = [0, 1, 14];
        this.__ua_key = "\u0000\u0001\u000e";
        this.__end_string = "cus";
        this.__version = [1, 0, 1, 5];
        this.__reg = [
            1937774191, 1226093241, 388252375, 3666478592,
            2842636476, 372324522, 3817729613, 2969243214
        ];
        this.__str = {
            "s0": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
            "s1": "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
            "s2": "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
            "s3": "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe",
            "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe"
        };

        // Initialize properties
        this.chunk = [];
        this.size = 0;
        this.reg = [...this.__reg];
        
        // Fixed UA code from Python version
        this.ua_code = [
            76, 98, 15, 131, 97, 245, 224, 133, 122, 199, 241, 166, 79, 34, 90, 191,
            128, 126, 122, 98, 66, 11, 14, 40, 49, 110, 110, 173, 67, 96, 138, 252
        ];

        this.browser = platform ? this.generateBrowserInfo(platform) : 
            "1536|742|1536|864|0|0|0|0|1536|864|1536|864|1536|742|24|24|MacIntel";
        this.browser_len = this.browser.length;
        this.browser_code = this.charCodeAt(this.browser);
    }

    // Generate random lists - equivalent to Python's list methods
    randomList(a = null, b = 170, c = 85, d = 0, e = 0, f = 0, g = 0) {
        const r = a || (Math.random() * 10000);
        const v = [r, parseInt(r) & 255, parseInt(r) >> 8];
        return [
            v[1] & b | d,
            v[1] & c | e,
            v[2] & b | f,
            v[2] & c | g
        ];
    }

    list1(randomNum = null) {
        return this.randomList(randomNum, 170, 85, 1, 2, 5, 45 & 170);
    }

    list2(randomNum = null) {
        return this.randomList(randomNum, 170, 85, 1, 0, 0, 0);
    }

    list3(randomNum = null) {
        return this.randomList(randomNum, 170, 85, 1, 0, 5, 0);
    }

    fromCharCode(...args) {
        return String.fromCharCode(...args);
    }

    // Generate string 1 - equivalent to Python's generate_string_1
    generateString1(randomNum1 = null, randomNum2 = null, randomNum3 = null) {
        return this.fromCharCode(...this.list1(randomNum1)) + 
               this.fromCharCode(...this.list2(randomNum2)) + 
               this.fromCharCode(...this.list3(randomNum3));
    }

    // SM3 Hash implementation
    reset() {
        this.chunk = [];
        this.size = 0;
        this.reg = [...this.__reg];
    }

    // Left rotation
    le(e, r) {
        r %= 32;
        return ((e << r) | (e >>> (32 - r))) >>> 0;
    }

    // Constants for SM3
    pe(e) {
        return e < 16 ? 2043430169 : 2055708042;
    }

    // Boolean functions
    he(e, r, t, n) {
        if (e < 16) {
            return (r ^ t ^ n) >>> 0;
        } else if (e < 64) {
            return ((r & t) | (r & n) | (t & n)) >>> 0;
        }
        throw new Error('Invalid e for he function');
    }

    ve(e, r, t, n) {
        if (e < 16) {
            return (r ^ t ^ n) >>> 0;
        } else if (e < 64) {
            return ((r & t) | (~r & n)) >>> 0;
        }
        throw new Error('Invalid e for ve function');
    }

    generateF(e) {
        const r = new Array(132);
        
        // First 16 words
        for (let t = 0; t < 16; t++) {
            r[t] = (e[4 * t] << 24) | (e[4 * t + 1] << 16) | 
                   (e[4 * t + 2] << 8) | e[4 * t + 3];
            r[t] >>>= 0;
        }

        // Extension
        for (let n = 16; n < 68; n++) {
            let a = r[n - 16] ^ r[n - 9] ^ this.le(r[n - 3], 15);
            a = a ^ this.le(a, 15) ^ this.le(a, 23);
            r[n] = (a ^ this.le(r[n - 13], 7) ^ r[n - 6]) >>> 0;
        }

        for (let n = 68; n < 132; n++) {
            r[n] = (r[n - 68] ^ r[n - 64]) >>> 0;
        }

        return r;
    }

    compress(a) {
        const f = this.generateF(a);
        const i = [...this.reg];
        
        for (let o = 0; o < 64; o++) {
            let c = this.le(i[0], 12) + i[4] + this.le(this.pe(o), o);
            c = (c & 0xFFFFFFFF) >>> 0;
            c = this.le(c, 7);
            const s = (c ^ this.le(i[0], 12)) >>> 0;

            let u = this.he(o, i[0], i[1], i[2]);
            u = (u + i[3] + s + f[o + 68]) >>> 0;

            let b = this.ve(o, i[4], i[5], i[6]);
            b = (b + i[7] + c + f[o]) >>> 0;

            i[3] = i[2];
            i[2] = this.le(i[1], 9);
            i[1] = i[0];
            i[0] = u;

            i[7] = i[6];
            i[6] = this.le(i[5], 19);
            i[5] = i[4];
            i[4] = (b ^ this.le(b, 9) ^ this.le(b, 17)) >>> 0;
        }

        for (let l = 0; l < 8; l++) {
            this.reg[l] = (this.reg[l] ^ i[l]) >>> 0;
        }
    }

    padArray(arr, length = 60) {
        while (arr.length < length) {
            arr.push(0);
        }
        return arr;
    }

    fill(length = 60) {
        const size = 8 * this.size;
        this.chunk.push(128);
        this.chunk = this.padArray(this.chunk, length);
        
        for (let i = 0; i < 4; i++) {
            this.chunk.push((size >>> (8 * (3 - i))) & 255);
        }
    }

    regToArray(a) {
        const o = new Array(32);
        for (let i = 0; i < 8; i++) {
            let c = a[i];
            o[4 * i + 3] = c & 255;
            c >>>= 8;
            o[4 * i + 2] = c & 255;
            c >>>= 8;
            o[4 * i + 1] = c & 255;
            c >>>= 8;
            o[4 * i] = c & 255;
        }
        return o;
    }

    charCodeAt(s) {
        return Array.from(s).map(char => char.charCodeAt(0));
    }

    decodeString(urlString) {
        return decodeURIComponent(urlString);
    }

    splitArray(arr, chunkSize = 64) {
        const result = [];
        for (let i = 0; i < arr.length; i += chunkSize) {
            result.push(arr.slice(i, i + chunkSize));
        }
        return result;
    }

    write(e) {
        this.size = e.length;
        if (typeof e === 'string') {
            e = this.decodeString(e);
            e = this.charCodeAt(e);
        }
        
        if (e.length <= 64) {
            this.chunk = [...e];
        } else {
            const chunks = this.splitArray(e, 64);
            for (let i = 0; i < chunks.length - 1; i++) {
                this.compress(chunks[i]);
            }
            this.chunk = [...chunks[chunks.length - 1]];
        }
    }

    sum(e, length = 60) {
        this.reset();
        this.write(e);
        this.fill(length);
        this.compress(this.chunk);
        return this.regToArray(this.reg);
    }

    // Generate method and params codes using SM3
    generateMethodCode(method = "GET") {
        return this.sum(this.sum(method + this.__end_string));
    }

    generateParamsCode(params) {
        return this.sum(this.sum(params + this.__end_string));
    }

    // List 4 - equivalent to Python's list_4
    list4(a, b, c, d, e, f, g, h, i, j, k, m, n, o, p, q, r) {
        return [
            44, a, 0, 0, 0, 0, 24, b, n, 0, c, d, 0, 0, 0, 1, 0, 239, e, o, f, g, 0, 0, 0, 0, h, 0, 0, 14,
            i, j, 0, k, m, 3, p, 1, q, 1, r, 0, 0, 0
        ];
    }

    // End check number
    endCheckNum(a) {
        let r = 0;
        for (const i of a) {
            r ^= i;
        }
        return r;
    }

    // Generate string 2 list
    generateString2List(urlParams, method = "GET", startTime = 0, endTime = 0) {
        startTime = startTime || Date.now();
        endTime = endTime || (startTime + Math.floor(Math.random() * 5) + 4);
        
        const paramsArray = this.generateParamsCode(urlParams);
        const methodArray = this.generateMethodCode(method);
        
        return this.list4(
            (endTime >> 24) & 255,
            paramsArray[21],
            this.ua_code[23],
            (endTime >> 16) & 255,
            paramsArray[22],
            this.ua_code[24],
            (endTime >> 8) & 255,
            (endTime >> 0) & 255,
            (startTime >> 24) & 255,
            (startTime >> 16) & 255,
            (startTime >> 8) & 255,
            (startTime >> 0) & 255,
            methodArray[21],
            methodArray[22],
            Math.floor(endTime / Math.pow(256, 4)),
            Math.floor(startTime / Math.pow(256, 4)),
            this.browser_len
        );
    }

    // RC4 encryption
    rc4Encrypt(plaintext, key) {
        const s = Array.from({length: 256}, (_, i) => i);
        let j = 0;

        for (let i = 0; i < 256; i++) {
            j = (j + s[i] + key.charCodeAt(i % key.length)) % 256;
            [s[i], s[j]] = [s[j], s[i]];
        }

        let i = 0;
        j = 0;
        const cipher = [];

        for (let k = 0; k < plaintext.length; k++) {
            i = (i + 1) % 256;
            j = (j + s[i]) % 256;
            [s[i], s[j]] = [s[j], s[i]];
            const t = (s[i] + s[j]) % 256;
            cipher.push(String.fromCharCode(s[t] ^ plaintext.charCodeAt(k)));
        }

        return cipher.join('');
    }

    // Generate string 2
    generateString2(urlParams, method = "GET", startTime = 0, endTime = 0) {
        const a = this.generateString2List(urlParams, method, startTime, endTime);
        const e = this.endCheckNum(a);
        a.push(...this.browser_code);
        a.push(e);
        return this.rc4Encrypt(this.fromCharCode(...a), "y");
    }

    // Generate result - equivalent to Python's generate_result
    generateResult(s, e = "s4") {
        const r = [];

        for (let i = 0; i < s.length; i += 3) {
            let n;
            if (i + 2 < s.length) {
                n = (s.charCodeAt(i) << 16) | (s.charCodeAt(i + 1) << 8) | s.charCodeAt(i + 2);
            } else if (i + 1 < s.length) {
                n = (s.charCodeAt(i) << 16) | (s.charCodeAt(i + 1) << 8);
            } else {
                n = s.charCodeAt(i) << 16;
            }

            const shifts = [18, 12, 6, 0];
            const masks = [0xFC0000, 0x03F000, 0x0FC0, 0x3F];
            
            for (let j = 0; j < 4; j++) {
                if (shifts[j] === 6 && i + 1 >= s.length) break;
                if (shifts[j] === 0 && i + 2 >= s.length) break;
                r.push(this.__str[e][(n & masks[j]) >> shifts[j]]);
            }
        }

        r.push("=".repeat((4 - r.length % 4) % 4));
        return r.join('');
    }

    // Generate browser info
    generateBrowserInfo(platform = "Win32") {
        const innerWidth = Math.floor(Math.random() * (1920 - 1280 + 1)) + 1280;
        const innerHeight = Math.floor(Math.random() * (1080 - 720 + 1)) + 720;
        const outerWidth = Math.floor(Math.random() * (1920 - innerWidth + 1)) + innerWidth;
        const outerHeight = Math.floor(Math.random() * (1080 - innerHeight + 1)) + innerHeight;
        const screenX = 0;
        const screenY = Math.random() < 0.5 ? 0 : 30;
        
        const valueList = [
            innerWidth, innerHeight, outerWidth, outerHeight,
            screenX, screenY, 0, 0, outerWidth, outerHeight,
            outerWidth, outerHeight, innerWidth, innerHeight,
            24, 24, platform
        ];
        
        return valueList.join('|');
    }

    // Main function - equivalent to Python's get_value
    getValue(urlParams, method = "GET", startTime = 0, endTime = 0, 
             randomNum1 = null, randomNum2 = null, randomNum3 = null) {
        
        // Convert dict to string if needed
        if (typeof urlParams === 'object') {
            urlParams = new URLSearchParams(urlParams).toString();
        }
        
        const string1 = this.generateString1(randomNum1, randomNum2, randomNum3);
        const string2 = this.generateString2(urlParams, method, startTime, endTime);
        const combinedString = string1 + string2;
        
        return this.generateResult(combinedString, "s4");
    }
}

// Usage example
function createABogus(platform = null) {
    return new ABogus(platform);
}

// Export for execjs
function get_a_bogus(urlParams, method = "GET", startTime = 0, endTime = 0, 
                     randomNum1 = null, randomNum2 = null, randomNum3 = null, platform = null) {
    const bogus = new ABogus(platform);
    return bogus.getValue(urlParams, method, startTime, endTime, randomNum1, randomNum2, randomNum3);
}

// For compatibility with existing code
function sign_datail(params, userAgent) {
    const bogus = new ABogus();
    return bogus.getValue(params, "GET");
}

function sign_reply(params, userAgent) {
    const bogus = new ABogus();
    return bogus.getValue(params, "GET");
}

// Export for Node.js if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ABogus, createABogus, get_a_bogus, sign_datail, sign_reply };
}
