# -*- coding: utf-8 -*-
"""交付前自检：只读，不改任何文件。

用法：
    python check_delivery.py --dir "C:\\Users\\xxx\\Desktop\\数据标注"
    python check_delivery.py --dir <目录> --docx "C:\\...\\标题.docx"

它会挡住这几类已经犯过的错：
    · 三张图尺寸不一致 / 有一张是方图（失误 6、10）
    · 三张图内容重复，下载串张（SOP 第 4 步）
    · 正文：被拆成两段，引语另起一段（失误 5 连带错误）
    · 表情小标题前没有空行（SOP 第 7 步）
    · 链接行加了标题/站名/来源（失误 9）
    · 链接后面还有别的东西
    · 文档里夹裸英文术语（红线 10）
"""
import argparse
import hashlib
import os
import re
import sys
import zipfile

XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
BANNED = ('md5', 'png', 'jpg', 'http', 'url', 'api', 'token', 'cookie')
URL_RE = re.compile(r'https?://|www\.|[A-Za-z0-9-]+\.(?:com|cn|net|org|io|co|me|tv|ai)\b', re.I)


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 16), b''):
            h.update(c)
    return h.hexdigest()


def find_image(directory, stem):
    """先看目录顶层，再看 images/ 子目录（整理时容易误放子目录）。"""
    for d in (directory, os.path.join(directory, 'images')):
        for ext in ('.png', '.PNG', '.jpg', '.jpeg', '.JPG', '.JPEG'):
            p = os.path.join(d, stem + ext)
            if os.path.exists(p):
                return p
    return None


def docx_paragraphs(path):
    """从 docx 里按顺序取出每段纯文本。"""
    import xml.etree.ElementTree as ET
    W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    out = []
    for p in root.iter(W + 'p'):
        txt = ''.join(t.text or '' for t in p.iter(W + 't'))
        out.append(txt)
    return out


def has_cjk(s):
    return any('\u4e00' <= ch <= '\u9fff' for ch in s)


def is_url(s):
    return bool(re.fullmatch(r'https?://\S+', s.strip()))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='交付目录')
    ap.add_argument('--docx', default=None, help='docx 路径；不给就取目录里最新的一个')
    ap.add_argument('--size', default='864x1152')
    args = ap.parse_args()

    tw, th = (int(v) for v in args.size.lower().split('x'))
    fails, warns = [], []

    if not os.path.isdir(args.dir):
        print(f'[FAIL] 目录不存在: {args.dir}')
        return 2

    # ---------- 图片 ----------
    print('=== 图片 ===')
    found = [s for s in ('1', '2', '3', '4') if find_image(args.dir, s)]
    expect = [str(i) for i in range(1, len(found) + 1)]
    if found != expect:
        fails.append(f'图片编号不连续：找到 {found or "无"}，应为 {expect}（命名只能 1/2/3/4）')
    if len(found) < 3:
        fails.append(f'只有 {len(found)} 张图，至少 3 张')

    hashes = {}
    for stem in found:
        p = find_image(args.dir, stem)
        from PIL import Image
        im = Image.open(p)
        fmt = (im.format or '').upper()
        ok = im.size == (tw, th)
        if not ok:
            fails.append(f'{stem} 尺寸 {im.size[0]}x{im.size[1]}，应为 {tw}x{th}')
        if fmt not in ('PNG', 'JPEG'):
            fails.append(f'{stem} 格式 {fmt}，只允许 png/jpg')
        hashes[stem] = md5(p)
        print(f'{stem}: {im.size[0]}x{im.size[1]}  {fmt}  {"OK" if ok else "尺寸不符"}')

    if len(hashes) >= 2 and len(set(hashes.values())) < len(hashes):
        fails.append('图片校验值有重复 —— 下载串张，必须单页重发')
        print('校验值: 有重复！')

    # ---------- 文档 ----------
    docx = args.docx
    if not docx:
        cands = [os.path.join(args.dir, f) for f in os.listdir(args.dir)
                 if f.lower().endswith('.docx') and not f.startswith('~$')]
        docx = max(cands, key=os.path.getmtime) if cands else None
    print('\n=== 文档 ===')
    if not docx or not os.path.exists(docx):
        fails.append('没找到 docx')
        print('未找到')
    else:
        ps = docx_paragraphs(docx)
        print(f'文件: {os.path.basename(docx)}  段落 {len(ps)} 个')

        if len(ps) < 8:
            fails.append('段落数过少，文档可能是空的')
        else:
            if not ps[0].startswith('分类：') or len(ps[0]) <= 3:
                fails.append(f'第 1 段应为「分类：xxx」，实际「{ps[0][:20]}」')
            if not ps[1].startswith('标题：') or len(ps[1]) <= 3:
                fails.append(f'第 2 段应为「标题：xxx」，实际「{ps[1][:20]}」')
            if not ps[2].startswith('正文：'):
                fails.append(f'第 3 段应为「正文：」，实际「{ps[2][:20]}」')
            elif len(ps[2]) < 20:
                fails.append('「正文：」后面没跟引语（引语被拆到下一段了？必须同段）')

            # 表情小标题：前面必须有空段
            head_idx = [i for i, t in enumerate(ps) if i >= 3 and t.strip() and _emoji_head(t)]
            if len(head_idx) != 3:
                fails.append(f'带表情的小标题应正好 3 个，实际 {len(head_idx)} 个')
            for i in head_idx:
                if i == 0 or ps[i - 1].strip() != '':
                    fails.append(f'第 {i + 1} 段「{ps[i][:14]}」前面没有空行')
            print(f'表情小标题: {len(head_idx)} 个')

            # 链接区
            link_i = next((i for i, t in enumerate(ps) if t.strip().startswith('文本链接')), None)
            if link_i is None:
                fails.append('没有「文本链接：」这一行')
            else:
                if ps[link_i].strip() != '文本链接：':
                    fails.append(f'链接行只能写「文本链接：」，实际「{ps[link_i].strip()[:30]}」'
                                 '（不许加标题/站名/来源）')
                rest = [t for t in ps[link_i + 1:] if t.strip()]
                if not rest:
                    fails.append('「文本链接：」后面没有 URL')
                else:
                    if not is_url(rest[0]):
                        fails.append(f'链接行下一行不是纯 URL：「{rest[0][:40]}」')
                    if len(rest) > 1:
                        fails.append(f'URL 后面还有 {len(rest) - 1} 段内容，链接之后不许再加东西')

            # 红线 11：除链接区那一行，全文不许出现网址
            if link_i is not None:
                after = [i for i in range(link_i + 1, len(ps)) if ps[i].strip()]
                allowed = after[0] if after else -1
                for i, t in enumerate(ps):
                    if i == allowed or not t.strip():
                        continue
                    m = URL_RE.search(t)
                    if m:
                        fails.append(f'红线 11：第 {i + 1} 段出现网址「{m.group(0)}」'
                                     f'（正文/板块里不许写网址，只有链接区那一行允许）')

            # 裸英文术语
            for t in ps:
                if not t.strip() or is_url(t):
                    continue
                low = t.lower()
                hit = [b for b in BANNED if b in low]
                if hit and not re.search(r'(https?://|\.com|\.cn)', t):
                    warns.append(f'疑似裸英文/术语 {hit}：「{t[:24]}」')

        print('结构检查完成')

    # ---------- 汇总 ----------
    print('\n=== 结论 ===')
    for w in warns:
        print(f'[警告] {w}')
    for f in fails:
        print(f'[不通过] {f}')
    if not fails:
        print('[PASS] 可以交付')
        return 0
    print(f'\n[FAIL] {len(fails)} 项不通过')
    return 1


def _emoji_head(t):
    """首字符是否是表情（含带变体符的）。"""
    ch = t.lstrip()[0]
    o = ord(ch)
    return (0x1F300 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF) or (0x2B00 <= o <= 0x2BFF)


if __name__ == '__main__':
    raise SystemExit(main())
