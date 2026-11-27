#!/usr/bin/env python3
import urllib.request
import re
import base64
import os
from datetime import datetime

OUTPUT_DIR = "output"

files = [
    ("http://www.xn--sss604efuw.net/tv/", os.path.join(OUTPUT_DIR, "ftr.json")),
    ("http://xn--z7x900a.net/tv",          os.path.join(OUTPUT_DIR, "fm.json")),
]


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "okhttp/3.12.13"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


SPIDER_RE = re.compile(
    r'"spider"\s*:\s*"(https?://[^";]+?/([^/";]+?);md5;([^"]+))"'
)


def extract_json_from_binary(text):
    """
    从 latin-1 文本里提取 JSON（括号配对版）：
      - 遍历每个 '{' 作为候选起点
      - 从该起点做括号配对（考虑字符串内的转义和引号）
      - 找到匹配的 '}' 后，检查中间内容是否包含 '"spider"'
      - 返回第一个配对成功且含 "spider" 的 JSON 片段
    返回 (json_str, start, end) 或 (None, -1, -1)
    """
    n = len(text)
    for start in range(n):
        if text[start] != '{':
            continue

        depth = 0
        in_str = False
        escape = False
        i = start
        end = -1

        while i < n:
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            i += 1

        if end == -1:
            continue  # 这个起点配不上，试下一个

        candidate = text[start:end + 1]

        # 至少包含 spider 字段，且长度合理，才认为是目标 JSON
        if '"spider"' in candidate and len(candidate) > 10:
            return candidate, start, end

    return None, -1, -1


def process_spider(json_text, base_dir):
    """下载 spider 文件，替换为 ./文件名;md5;xxx"""
    changed = False

    def repl(m):
        nonlocal changed
        full_url, filename, md5 = m.group(1), m.group(2), m.group(3)
        real_url = full_url.split(";md5;")[0]
        spider_path = os.path.join(base_dir, filename)
        try:
            raw = http_get(real_url)
            with open(spider_path, "wb") as f2:
                f2.write(raw)
            log(f"  spider 文件已下载：{spider_path}，大小 {len(raw)} 字节")
        except Exception as e:
            log(f"  spider 文件下载失败 {real_url}: {e}")
            return m.group(0)
        changed = True
        return f'"spider":"./{filename};md5;{md5}"'

    new_text = SPIDER_RE.sub(repl, json_text)
    return new_text, changed


def save_json_and_process(json_text, save_path):
    """统一出口：处理 spider → 写 JSON 文件"""
    base_dir = os.path.dirname(save_path) or "."
    new_text, changed = process_spider(json_text, base_dir)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    log(f"保存 JSON：{save_path}，大小 {os.path.getsize(save_path)} 字节"
        + ("（spider 已替换）" if changed else "（无 spider 替换）"))


def download(url, save_path):
    raw = http_get(url)

    # 情况 A：直接是 JSON
    if raw.lstrip()[:1] in (b'{', b'['):
        json_text = raw.decode('utf-8', errors='ignore')
        save_json_and_process(json_text, save_path)
        return

    # 情况 B：图片伪装（PNG 等二进制），先转 latin-1
    text = raw.decode('latin-1', errors='ignore')

    # B-1：有 8字符** + Base64 标记（肥猫 ftr 格式）
    match = re.search(r'[A-Za-z0-9]{8}\*\*', text)
    if match:
        b64_str = text[match.end():].strip()
        padding = len(b64_str) % 4
        if padding:
            b64_str += '=' * (4 - padding)
        try:
            decoded = base64.b64decode(b64_str)
            json_text = decoded.decode('utf-8')
            save_json_and_process(json_text, save_path)
            return
        except Exception as e:
            log(f"Base64 解码失败，尝试提取 JSON：{e}")

    # B-2：没有 Base64 标记，用括号配对从 latin-1 文本里提取 { ... }
    json_candidate, start, end = extract_json_from_binary(text)
    if json_candidate is None:
        with open(save_path, 'wb') as f:
            f.write(raw)
        log(f"未找到 JSON，已原样保存：{save_path}，大小 {os.path.getsize(save_path)} 字节")
        return

    log(f"从二进制中提取 JSON：偏移 {start}~{end}，长度 {len(json_candidate)}")
    save_json_and_process(json_candidate, save_path)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url, save_path in files:
        try:
            download(url, save_path)
        except Exception as e:
            log(f"下载失败 {url}: {e}")


if __name__ == "__main__":
    main()
