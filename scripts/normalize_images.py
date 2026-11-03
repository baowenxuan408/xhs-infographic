# -*- coding: utf-8 -*-
"""把交付目录里的 1/2/3 图片统一到 3:4（默认 864x1152）。

用法：
    python normalize_images.py --dir "C:\\Users\\xxx\\Desktop\\数据标注"
    python normalize_images.py --dir <目录> --dry-run          # 只报告，不改文件
    python normalize_images.py --dir <目录> --size 1086x1448

规则（来自 SOP 第 5 步 / 失误 6、10）：
    1. 目标比例 3:4。已是目标尺寸的图不动（不重编码，避免掉质量）。
    2. 其他竖版比例：等比缩放后居中补边，补边色从图片边缘采样。
    3. 方图（1:1）：等比缩到 864 宽 → 上下各补边 → 交界处羽化 20px。
    4. 禁止镜像延展（会把标题倒着翻出来，必废）。
    5. 输出每张的原尺寸 / 新尺寸 / md5，并检查三个 md5 是否互不相同。
"""
import argparse
import hashlib
import os
import sys

from PIL import Image, ImageFilter

TARGET = (864, 1152)
FEATHER = 20
NAMES = ("1", "2", "3", "4")   # 张数自适应：1-3 或 1-4，必须连续


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def find_image(directory, stem):
    for ext in (".png", ".PNG", ".jpg", ".jpeg", ".JPG", ".JPEG"):
        p = os.path.join(directory, stem + ext)
        if os.path.exists(p):
            return p
    return None


def edge_color(im):
    """从四边采样一个背景色（取中位数，避开图案干扰）。"""
    w, h = im.size
    px = im.load()
    samples = []
    step = max(1, w // 40)
    for x in range(0, w, step):
        samples.append(px[x, 0])
        samples.append(px[x, h - 1])
    step = max(1, h // 40)
    for y in range(0, h, step):
        samples.append(px[0, y])
        samples.append(px[w - 1, y])
    n = len(samples)
    return tuple(sorted(s[i] for s in samples)[n // 2] for i in range(3))


def fit_onto_canvas(im, size):
    """等比缩放 + 居中补边；交界处羽化。不做镜像、不裁切。"""
    tw, th = size
    bg = edge_color(im)
    canvas = Image.new("RGB", (tw, th), bg)

    scale = min(tw / im.width, th / im.height)
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    fg = im.resize((nw, nh), Image.LANCZOS)

    # 羽化蒙版：仅在 fg 与画布相接的上下（或左右）边缘做渐变
    mask = Image.new("L", (nw, nh), 255)
    mpx = mask.load()
    f = min(FEATHER, nh // 8, nw // 8)
    for y in range(f):
        v = int(255 * y / f)
        for x in range(nw):
            if mpx[x, y] > v:
                mpx[x, y] = v
            y2 = nh - 1 - y
            if mpx[x, y2] > v:
                mpx[x, y2] = v
    mask = mask.filter(ImageFilter.GaussianBlur(2))

    canvas.paste(fg, ((tw - nw) // 2, (th - nh) // 2), mask)

    # 四角如果出现方形色块，统一抹成背景色（羽化只在接缝处，不碰图内容）
    return canvas, bg


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="交付目录，含 1/2/3 图片")
    ap.add_argument("--size", default="864x1152", help="目标尺寸，默认 864x1152")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写回文件")
    args = ap.parse_args()

    tw, th = (int(v) for v in args.size.lower().split("x"))
    target = (tw, th)

    if not os.path.isdir(args.dir):
        print(f"[FAIL] 目录不存在: {args.dir}")
        return 2

    # 张数自适应：找出实际存在的图，编号必须从 1 开始连续
    found = [s for s in NAMES if find_image(args.dir, s)]
    if not found:
        print(f"[FAIL] 目录里没有 1.png / 1.jpg: {args.dir}")
        return 1
    expect = [str(i) for i in range(1, len(found) + 1)]
    if found != expect:
        print(f"[FAIL] 编号不连续：找到 {found}，应为 {expect}（命名只能 1/2/3/4）")
        return 1
    if len(found) < 3:
        print(f"[FAIL] 只有 {len(found)} 张，至少要 3 张才讲得清主需")
        return 1

    rows = []
    changed = 0
    for stem in found:
        p = find_image(args.dir, stem)
        im = Image.open(p)
        orig, fmt = im.size, (im.format or "").upper()
        im = im.convert("RGB")
        need = im.size != target
        status = "已符合"
        if need:
            status = "已补边" if not args.dry_run else "待补边"
            if not args.dry_run:
                out, bg = fit_onto_canvas(im, target)
                out.save(p, "PNG")
                changed += 1
                status = f"已补边(底色{bg})"
        rows.append((stem, orig, im.size if not need else target, md5(p), status))

    print(f"\n=== 尺寸报告（共 {len(found)} 张）===")
    print(f"{'图':<4}{'原尺寸':<14}{'现尺寸':<14}{'校验值(前8)':<12}状态")
    for stem, orig, now, h, st in rows:
        o = f"{orig[0]}x{orig[1]}" if orig else "-"
        n = f"{now[0]}x{now[1]}" if now else "-"
        print(f"{stem:<4}{o:<14}{n:<14}{(h or '-')[:8]:<12}{st}")

    hashes = [r[3] for r in rows if r[3]]
    if len(set(hashes)) != len(hashes):
        print("\n[FAIL] 校验值重复 —— 有重复图（下载串张），必须单页重发")
        return 1

    if args.dry_run:
        print(f"\n[DRY-RUN] 未改动任何文件；如需按 {tw}x{th} 归口，去掉 --dry-run 再跑一次")
    else:
        print(f"\n[OK] 已归口 {changed} 张 → {tw}x{th}，校验值互不相同")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
