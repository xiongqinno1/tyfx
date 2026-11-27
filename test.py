#!/usr/bin/env python3
import urllib.request
import re
import base64
import os
from datetime import datetime

OUTPUT_DIR = "output"

files = [
    ("http://www.xn--sss604efuw.net/tv/",
     os.path.join(OUTPUT_DIR, "ftr.json")),
    ("http://xn--z7x900a.net/tv",
     os.path.join(OUTPUT_DIR, "fm.json")),
    
]


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "okhttp/3.12.13"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# 匹配整个 "spider": "https://....;md5;xxxx"
#  group(1) = 完整 URL（含 ;md5;xxxx）
#  group(2) = URL 去掉 ;md5; 后的真实下载地址
#  group(3) = 文件名（URL 最后一段）
#  group(4) = md5 值
SPIDER_RE = re.compile(
    r'"spider"\s*:\s*"(https?://[^";]+?/([^/";]+?);md5;([^"]+))"'
)
# 如果 URL 里可能有 ";" 出现在路径里，这种简单正则已经够用


def process_json_file(json_path):
    """
    读入已写好的 JSON 文件：
      1. 扫描 "spider": "https://.../文件名;md5;xxx"
      2. 从完整 URL 中去掉 ;md5;xxx 得到 real_url
      3. 下载 real_url -> base_dir/文件名
      4. 替换成 "spider":"./文件名;md5;xxx"
    然后写回。
    """
    base_dir = os.path.dirname(json_path) or "."

    with open(json_path, "r", encoding="utf-8", errors="ignore") as f:
        json_text = f.read()

    changed = False

    def repl(m):
        nonlocal changed
        full_url = m.group(1)      # https://.../文件名;md5;xxxx
        filename = m.group(3)      # 文件名
        md5 = m.group(4)           # md5 值

        # 去掉 ;md5;xxxx 得到真实下载 URL
        real_url = full_url.split(";md5;")[0]

        save_path = os.path.join(base_dir, filename)

        # 下载文件（替换之前必须先下）
        try:
            raw = http_get(real_url)
            with open(save_path, "wb") as f2:
                f2.write(raw)
            log(f"  spider 文件已下载：{save_path}，大小 {len(raw)} 字节")
        except Exception as e:
            log(f"  spider 文件下载失败 {real_url}: {e}")
            return m.group(0)   # 下载失败保留原样

        changed = True
        return f'"spider":"./{filename};md5;{md5}"'

    new_text = SPIDER_RE.sub(repl, json_text)

    if changed:
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        log(f"已回写 spider 替换：{json_path}")


def download(url, save_path):
    raw = http_get(url)

    # 1. 直接是 JSON
    if raw.lstrip()[:1] in (b'{', b'['):
        json_text = raw.decode('utf-8', errors='ignore')
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(json_text)
        log(f"直接保存 JSON：{save_path}，大小 {os.path.getsize(save_path)} 字节")
        process_json_file(save_path)
        return

    # 2. 图片伪装：找 8位字母数字 + ** 标记
    text = raw.decode('latin-1', errors='ignore')
    match = re.search(r'[A-Za-z0-9]{8}\*\*', text)

    if not match:
        text_check = raw.decode('utf-8', errors='ignore')
        if '"spider"' not in text_check:
            with open(save_path, 'wb') as f:
                f.write(raw)
            log(f"未找到标记且无 spider，已原样保存：{save_path}，大小 {os.path.getsize(save_path)} 字节")
            return
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text_check)
        log(f"保存 JSON：{save_path}，大小 {os.path.getsize(save_path)} 字节")
        process_json_file(save_path)
        return

    # 3. Base64 解码出 JSON
    b64_str = text[match.end():].strip()
    padding = len(b64_str) % 4
    if padding:
        b64_str += '=' * (4 - padding)

    try:
        decoded = base64.b64decode(b64_str)
        json_text = decoded.decode('utf-8')
    except Exception as e:
        log(f"Base64 解码失败：{e}")
        return

    with open(save_path, 'w', encoding='utf-8') as f:
        f.write(json_text)
    log(f"解码成功并保存 JSON：{save_path}，大小 {os.path.getsize(save_path)} 字节")
    process_json_file(save_path)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url, save_path in files:
        try:
            download(url, save_path)
        except Exception as e:
            log(f"下载失败 {url}: {e}")


if __name__ == "__main__":
    main()
