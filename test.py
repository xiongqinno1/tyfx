#!/usr/bin/env python3
import urllib.request
import re
import base64
import os
from datetime import datetime

# 输出目录（GitHub Actions 中会随 artifact 上传或提交回仓库）
OUTPUT_DIR = "output"

# ① 要下载的文件列表：(url, 保存路径)
files = [
    ("http://www.xn--sss604efuw.net/tv/",
     os.path.join(OUTPUT_DIR, "ftr.json")),
    ("https://file.icve.com.cn/file_doc/874/405/DAB654F794A271C3D7A33D18ACFBFA95.jpg",
     os.path.join(OUTPUT_DIR, "DAB654F794A271C3D7A33D18ACFBFA95.jpg")),
    ("http://xn--z7x900a.net/tv",
     os.path.join(OUTPUT_DIR, "fm.json")),
    ("https://img2.gelonghui.com/library/46da6-aa33493f-1c1d-4f35-9990-0be4bdbf0c64.png",
     os.path.join(OUTPUT_DIR, "46da6-aa33493f-1c1d-4f35-9990-0be4bdbf0c64.png")),
]


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ② 带解码功能的 download 函数
def download(url, save_path):
    req = urllib.request.Request(url, headers={"User-Agent": "okhttp/3.12.13"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    # 1. 直接是 JSON？
    if raw.lstrip()[:1] in (b'{', b'['):
        json_text = raw.decode('utf-8', errors='ignore')

        def repl(m):
            path = m.group(1)
            filename = path.rstrip('/').split('/')[-1]
            return f'"spider":"./{filename};md5;'

        json_text = re.sub(r'"spider":\s*"([^;]+);md5;', repl, json_text)

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(json_text)
        log(f"直接保存 JSON（已替换 spider 路径）：{save_path}，大小 {os.path.getsize(save_path)} 字节")
        return

    # 2. 图片伪装格式，转 latin-1 搜索标记
    text = raw.decode('latin-1', errors='ignore')
    match = re.search(r'[A-Za-z0-9]{8}\*\*', text)
    if not match:
        text_check = raw.decode('utf-8', errors='ignore')

        if '"spider"' not in text_check:
            with open(save_path, 'wb') as f:
                f.write(raw)
            log(f"未找到标记且无 spider，已原样保存：{save_path}，大小 {os.path.getsize(save_path)} 字节")
            return

        def repl(m):
            path = m.group(1)
            filename = path.rstrip('/').split('/')[-1]
            return f'"spider":"./jar/{filename};md5;'

        new_text = re.sub(r'"spider":\s*"([^;]+);md5;', repl, text_check)

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(new_text)
        log(f"已替换 spider 路径并保存：{save_path}，大小 {os.path.getsize(save_path)} 字节")
        return

    # 3. 提取标记之后的 Base64 内容
    b64_str = text[match.end():].strip()

    # 4. 补全填充并解码
    padding = len(b64_str) % 4
    if padding:
        b64_str += '=' * (4 - padding)

    try:
        decoded = base64.b64decode(b64_str)
        json_text = decoded.decode('utf-8')

        def repl(m):
            path = m.group(1)
            filename = path.rstrip('/').split('/')[-1]
            return f'"spider":"./{filename};md5;'

        json_text = re.sub(r'"spider":\s*"([^;]+);md5;', repl, json_text)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(json_text)
        log(f"解码成功：{save_path}，大小 {os.path.getsize(save_path)} 字节")
    except Exception as e:
        log(f"Base64 解码失败：{e}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url, save_path in files:
        try:
            download(url, save_path)
        except Exception as e:
            log(f"下载失败 {url}: {e}")


if __name__ == "__main__":
    main()