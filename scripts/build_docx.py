# -*- coding: utf-8 -*-
"""按 copy.json 生成标注 docx（沿用既有版式）。

用法：
    python build_docx.py --copy copy_20261103_三轮车.json --out "C:\\...\\数据标注\\三轮车打不着火先查这仨.docx"

copy.json 结构：
{
  "category": "生活",
  "title":    "三轮车打不着火先查这仨",
  "lead":     "开头的真人分享引语，一整段",
  "sections": [
    {"emoji": "🔋", "heading": "先看电瓶桩头别急着换新", "body": ["1. ...", "2. ..."]},
    {"emoji": "🔥", "heading": "油和火各摸一下",        "body": ["1. ..."]},
    {"emoji": "🛠️", "heading": "还不行就别硬打了",      "body": ["1. ...", "2. ..."]}
  ],
  "ending": "只做总结的最后一句",
  "link":   "https://..."
}

为什么要这个中间文件：文案的“结构”和“排版”分开。结构错了在 json 里一改就重出，
不用重跑浏览器；排版永远由这个脚本决定，不会因为每次手写 XML 而漂移。
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from xml.sax.saxutils import escape

RPR = '<w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/></w:rPr>'
# 表情单独指定字体，否则 Word/WPS 显示豆腐块（SOP 第 7 步硬要求）
RPR_EMOJI = ('<w:rPr><w:rFonts w:ascii="Segoe UI Emoji" w:hAnsi="Segoe UI Emoji" '
             'w:eastAsia="Microsoft YaHei" w:hint="eastAsia"/>'
             '<w:lang w:val="en-US" w:eastAsia="zh-CN"/></w:rPr>')


def run(text, emoji=False):
    if not text:
        return ''
    rpr = RPR_EMOJI if emoji else RPR
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(text='', emoji=False):
    return f'<w:p><w:pPr>{RPR}</w:pPr>{run(text, emoji)}</w:p>'


URL_RE = re.compile(r'https?://|www\.|[A-Za-z0-9-]+\.(?:com|cn|net|org|io|co|me|tv|ai)\b', re.I)


def has_url(text):
    """红线 11：除 link 字段外，任何文案位置出现网址都算违规。"""
    return bool(text) and bool(URL_RE.search(text))


def pick(text):
    m = URL_RE.search(text or '')
    return m.group(0) if m else (text or '')[:24]


def validate(d):
    errs = []
    for k in ('category', 'title', 'lead', 'sections', 'ending', 'link'):
        if not d.get(k):
            errs.append(f'缺字段: {k}')
    secs = d.get('sections') or []
    if len(secs) != 3:
        errs.append(f'板块必须正好 3 个，当前 {len(secs)} 个（红线：只要三个板块）')
    for i, s in enumerate(secs, 1):
        if not s.get('emoji'):
            errs.append(f'第 {i} 个板块缺表情')
        if not s.get('heading'):
            errs.append(f'第 {i} 个板块缺小标题')
        if not s.get('body'):
            errs.append(f'第 {i} 个板块正文为空')
    link = (d.get('link') or '').strip()
    if link and not link.startswith(('http://', 'https://')):
        errs.append('链接必须是完整 URL')
    if '\n' in (d.get('lead') or ''):
        errs.append('引语必须是一整段，不能含换行（正文：与引语同段）')
    # 红线 11：除 link 字段外，任何位置都不许出现网址
    for field, val in (('分类', d.get('category')), ('标题', d.get('title')),
                       ('引语', d.get('lead')), ('最后一句', d.get('ending'))):
        if has_url(val):
            errs.append(f'红线 11：{field} 里出现网址「{pick(val)}」，'
                        '用中文描述入口（「打开官网帮助页面」），全文档只允许链接区有一处网址')
    for i, s in enumerate(secs, 1):
        for txt in [s.get('heading', '')] + list(s.get('body') or []):
            if has_url(txt):
                errs.append(f'红线 11：第 {i} 板块正文出现网址「{pick(txt)}」，必须删掉或改成中文入口')
    return errs


def build(d):
    """返回段落列表：[(text, is_emoji), ...]"""
    ps = [
        (f"分类：{d['category']}", False),
        (f"标题：{d['title']}", False),
        (f"正文：{d['lead']}", False),   # 与引语同段，中间不换行
    ]
    for s in d['sections']:
        ps.append(('', False))                      # 表情小标题前必须空行
        ps.append((f"{s['emoji']} {s['heading']}", True))
        for line in s['body']:
            ps.append((line, False))
    ps.append(('', False))
    ps.append((d['ending'], False))
    ps.append(('', False))
    ps.append(('文本链接：', False))                 # 冒号后什么都不加
    ps.append(('', False))
    ps.append((d['link'].strip(), False))
    return ps


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    default_tpl = os.path.join(os.path.dirname(here), 'assets', 'template.docx')

    ap = argparse.ArgumentParser()
    ap.add_argument('--copy', required=True, help='copy.json 路径')
    ap.add_argument('--out', required=True, help='输出的 docx 路径')
    ap.add_argument('--template', default=default_tpl, help='样式模板 docx')
    args = ap.parse_args()

    with open(args.copy, encoding='utf-8') as f:
        d = json.load(f)

    errs = validate(d)
    if errs:
        print('[FAIL] copy.json 不合规：')
        for e in errs:
            print('  -', e)
        return 1

    if not os.path.exists(args.template):
        print(f'[FAIL] 模板不存在: {args.template}')
        return 2

    ps = build(d)
    z = zipfile.ZipFile(args.template)
    xml = z.read('word/document.xml').decode('utf-8')
    i0 = xml.index('<w:body>') + len('<w:body>')
    tail = xml[xml.rindex('<w:sectPr'):]
    new_xml = xml[:i0] + ''.join(para(t, e) for t, e in ps) + tail

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    tmp = args.out + '.tmp'
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
            for it in z.infolist():
                if it.filename == 'word/document.xml':
                    zo.writestr(it, new_xml.encode('utf-8'))
                else:
                    zo.writestr(it, z.read(it.filename))
        z.close()
        shutil.move(tmp, args.out)
    except PermissionError:
        z.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        print('[FAIL] 目标文档被占用 —— 先关掉 Word / WPS 再写（否则报 WinError 5/32）')
        return 3

    print(f'[OK] {args.out}')
    print(f'     段落 {len(ps)} 个，板块 {len(d["sections"])} 个，大小 {os.path.getsize(args.out)} 字节')
    print(f'     分类={d["category"]} 标题={d["title"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
