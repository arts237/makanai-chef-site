#!/usr/bin/env python3
"""記事ごとのシェア画像（OGP・1200×630）を作る（M-013 第1段）。

- 対象: layout: article のページ（保存方法の記事・早見表・/storage/・/shopping/・/stock/）
- 画像: assets/images/og/<スラッグ>.png。front matter の title（「｜」の前が見出し、後ろが補足）から作る
- front matter に `og_photo: true` がある記事は、写真に差し替えた記事なので作り直さない（第2段）
- 各記事の front matter の image: を assets/images/og/<スラッグ>.png に書き換える
- 作った画像の元（見出し・補足・ラベル・型の版）を assets/images/og/manifest.json に控え、
  元が変わったときだけ作り直す（フォントの版の違いで毎回差分が出ないように）

使い方: python scripts/make_og.py        # 作る・書き換える
        python scripts/make_og.py --check  # 差分があれば失敗（CI用）
フォント: Noto Sans CJK（Ubuntu の fonts-noto-cjk）。環境変数 OG_FONT_BOLD / OG_FONT_REG で変えられる
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images", "og")
W, H = 1200, 630
BG = (251, 247, 240)       # --bg
INK = (58, 50, 44)         # --ink
INK_SOFT = (94, 85, 77)    # --ink-soft
ACCENT = (181, 85, 58)     # --accent
ACCENT_SOFT = (246, 230, 222)
LINE = (233, 224, 211)

STYLE_VERSION = 1  # 画像の型を変えたら上げる（全部作り直す）
MANIFEST = os.path.join(OUT, "manifest.json")

FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/noto-cjk"]


def font_path(env, name):
    if os.environ.get(env):
        return os.environ[env]
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    sys.exit(f"フォントが見つからない: {name}（fonts-noto-cjk を入れるか {env} を指定）")


BOLD = "NotoSansCJK-Bold.ttc"
REG = "NotoSansCJK-Regular.ttc"
JP = 0  # .ttc の中の日本語（JP）の番号


def f(name, size):
    # フォントは画像を作るときだけ探す（--check はフォントなしで動く）
    env = "OG_FONT_BOLD" if name == BOLD else "OG_FONT_REG"
    return ImageFont.truetype(font_path(env, name), size, index=JP)


def pages():
    out = subprocess.run(["git", "ls-files", "*.html", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    for rel in out.split():
        if rel.startswith(("_", "vendor/")):
            continue
        txt = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
        if not m or not re.search(r"^layout:\s*article\s*$", m.group(1), re.M):
            continue
        yield rel, txt, m.group(1)


def fm_value(fm, key):
    m = re.search(rf'^{key}:\s*"?(.*?)"?\s*$', fm, re.M)
    return m.group(1) if m else ""


def slug_of(fm):
    p = fm_value(fm, "permalink").strip("/")
    return (p.split("/")[-1] or "index") if p else None


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= width:
            cur += ch
        else:
            # 行頭に句読点・閉じ括弧が来ないように1文字戻す
            if ch in "、。）」』・！？" and cur:
                lines.append(cur[:-1]); cur = cur[-1] + ch
            else:
                lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def render(title, sub, label):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    pad = 80
    # 上の帯（アクセント）
    d.rectangle([0, 0, W, 14], fill=ACCENT)
    # ラベル
    lf = f(BOLD, 30)
    lw = d.textlength(label, font=lf)
    d.rounded_rectangle([pad, 70, pad + lw + 40, 70 + 52], radius=26, fill=ACCENT_SOFT)
    d.text((pad + 20, 70 + 7), label, font=lf, fill=ACCENT)
    # 見出し（長さで字の大きさを変える）
    # 1行に収まる大きさ（60以上）を探し、収まらなければ2行に分けて左右の長さをそろえる
    tl = None
    for size in (84, 76, 68, 60):
        tf = f(BOLD, size)
        if d.textlength(title, font=tf) <= W - pad * 2:
            tl = [title]
            break
    if tl is None:
        size = 72
        tf = f(BOLD, size)
        half = d.textlength(title, font=tf) / 2 + size
        tl = wrap(d, title, tf, min(W - pad * 2, half))
    y = 160
    for line in tl[:3]:
        d.text((pad, y), line, font=tf, fill=INK)
        y += int(size * 1.3)
    # 補足（「｜」の後ろ）
    if sub:
        sf = f(REG, 36)
        for line in wrap(d, sub, sf, W - pad * 2)[:2]:
            d.text((pad, y + 14), line, font=sf, fill=INK_SOFT)
            y += 50
    # 下の帯: アイコン・サイト名・ドメイン
    d.line([pad, H - 120, W - pad, H - 120], fill=LINE, width=3)
    logo = Image.open(os.path.join(ROOT, "assets", "images", "logo.png")).convert("RGBA").resize((64, 64))
    mask = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 63, 63], fill=255)
    im.paste(logo, (pad, H - 96), mask)
    d.text((pad + 84, H - 90), "まかないシェフ", font=f(BOLD, 34), fill=INK)
    dom = "makanai-chef.com"
    df = f(REG, 30)
    d.text((W - pad - d.textlength(dom, font=df), H - 84), dom, font=df, fill=INK_SOFT)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main():
    check = "--check" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    changed = []
    manifest = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    new_manifest = {}
    for rel, txt, fm in pages():
        slug = slug_of(fm)
        if not slug:
            continue
        img_rel = f"assets/images/og/{slug}.png"
        if not re.search(r"^og_photo:\s*true\s*$", fm, re.M):
            full = fm_value(fm, "title")
            title, _, sub = full.partition("｜")
            if not sub:
                # 「｜」がないページは description の最初の文を補足にする
                sub = re.split(r"(?<=。)", fm_value(fm, "description"))[0]
            label = "保存方法ガイド" if "/storage/" in fm_value(fm, "permalink") else "まかないシェフの記事"
            if label == title.strip():
                label = "まかないシェフの記事"
            key = hashlib.sha256(json.dumps([STYLE_VERSION, title.strip(), sub.strip(), label], ensure_ascii=False).encode()).hexdigest()[:16]
            new_manifest[slug] = key
            path = os.path.join(ROOT, img_rel)
            if manifest.get(slug) != key or not os.path.exists(path):
                changed.append(img_rel)
                if not check:
                    open(path, "wb").write(render(title.strip(), sub.strip(), label))
        elif not os.path.exists(os.path.join(ROOT, img_rel)):
            changed.append(img_rel + "（写真がない）")
        want = f"image: /{img_rel}"
        if re.search(r"^image:.*$", fm, re.M):
            new_fm = re.sub(r"^image:.*$", want, fm, count=1, flags=re.M)
        else:
            new_fm = fm + "\n" + want
        if new_fm != fm:
            changed.append(rel)
            if not check:
                open(os.path.join(ROOT, rel), "w", encoding="utf-8").write(txt.replace(fm, new_fm, 1))
    if new_manifest != {k: v for k, v in manifest.items() if k in new_manifest} or set(manifest) - set(new_manifest):
        if "manifest.json" not in changed:
            changed.append("assets/images/og/manifest.json")
        if not check:
            with open(MANIFEST, "w", encoding="utf-8") as fp:
                json.dump(dict(sorted(new_manifest.items())), fp, ensure_ascii=False, indent=1)
                fp.write("\n")
    if changed:
        print(("作り直しが必要: " if check else "更新: ") + ", ".join(changed))
        if check:
            print("::error::シェア画像（scripts/make_og.py）を作り直していない記事があります。python scripts/make_og.py を実行してコミットしてください")
            sys.exit(1)
    else:
        print("シェア画像: 変更なし")


if __name__ == "__main__":
    main()
