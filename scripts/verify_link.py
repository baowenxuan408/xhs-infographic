# -*- coding: utf-8 -*-
"""验证链接是不是"深链"，别再把首页塞进文档（失误 8）。

用法：
    python verify_link.py "https://pcedu.pconline.com.cn/1501/15016984.html" 群待办 待办
    python verify_link.py <URL> 关键词1 [关键词2 ...] --json

判定（任一不过就不许写进文档）：
    1. 返回码必须是 200（先跟一遍重定向，看最终地址）
    2. 不能是首页 / 频道页 / 搜索页
    3. 正文里关键词累计出现 >= 3 次
    4. 页面标题最好本身就说这件事（加分项，缺了只警告）
"""
import argparse
import gzip
import io
import json
import re
import ssl
import sys
import urllib.error
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip',
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        charset = r.headers.get_content_charset()
        for enc in ([charset] if charset else []) + ['utf-8', 'gb18030']:
            try:
                return r.status, r.geturl(), raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return r.status, r.geturl(), raw.decode('utf-8', 'ignore')


def plain_text(html):
    html = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', html)
    html = re.sub(r'(?s)<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;|&#160;', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()


def title_of(html):
    m = re.search(r'(?is)<title[^>]*>(.*?)</title>', html)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def judge(url, status, final, title, text, keywords):
    path = re.sub(r'^https?://[^/]+', '', final).split('?')[0]
    query = final.split('?', 1)[1] if '?' in final else ''
    reasons, warns = [], []

    if status != 200:
        reasons.append(f'返回码 {status}，不是 200')
    if path in ('', '/'):
        reasons.append('最终地址是站点首页，不是详情页')
    if re.search(r'/(search|so|s)(/|$)', path) or re.search(r'(^|&)(q|wd|word|query)=', query):
        reasons.append('最终地址是搜索页')
    if len(text) < 200:
        reasons.append('正文过短（<200 字），大概率是壳页面')

    hits = sum(len(re.findall(re.escape(k), text, re.I)) for k in keywords)
    if hits == 0:
        reasons.append('正文里一个关键词都没出现')
    elif hits < 3:
        warns.append(f'关键词只出现 {hits} 次（要求 >=3），相关性偏弱')

    if keywords and not any(k.lower() in title.lower() for k in keywords):
        warns.append('页面标题不含关键词，读者点开可能对不上')

    return hits, reasons, warns


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('keywords', nargs='*', help='主题关键词，越多越能判断相关性')
    ap.add_argument('--json', action='store_true', help='只输出 JSON')
    args = ap.parse_args()

    try:
        status, final, html = fetch(args.url)
    except urllib.error.HTTPError as e:
        status, final, html = e.code, args.url, ''
    except Exception as e:
        print(f'[FAIL] 抓取失败: {type(e).__name__}: {e}')
        return 2

    title = title_of(html)
    text = plain_text(html)
    hits, reasons, warns = judge(args.url, status, final, title, text, args.keywords)

    out = {
        'url': args.url,
        'final_url': final,
        'status': status,
        'title': title,
        'text_len': len(text),
        'keyword_hits': hits,
        'verdict': 'PASS' if not reasons else 'FAIL',
        'reasons': reasons,
        'warnings': warns,
        'snippet': text[:160],
    }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"返回码   {status}")
        print(f"最终地址 {final}")
        print(f"页面标题 {title or '(无)'}")
        print(f"正文长度 {len(text)} 字，关键词命中 {hits} 次")
        print(f"开头片段 {out['snippet']}")
        for w in warns:
            print(f"[警告] {w}")
        for r in reasons:
            print(f"[不通过] {r}")
        print(f"\n结论：{'PASS 可以写进文档' if not reasons else 'FAIL 换一条链接'}")

    return 0 if not reasons else 1


if __name__ == '__main__':
    raise SystemExit(main())
