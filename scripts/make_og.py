#!/usr/bin/env python3
"""記事ごとのシェア画像（OGP・1200×630）を作る（M-013 第1段）。

- 対象: layout: article のページ（保存方法の記事・早見表・/storage/・/shopping/・/stock/）
- 画像: assets/images/og/<スラッグ>.png。front matter の title（「｜」の前が見出し、後ろが補足）から作る
- front matter に `og_photo: true` がある記事は、写真に差し替えた記事なので作り直さない（第2段）。
  image: に書いた写真をそのまま使う（Xのキャッシュを避けるため、写真は別の名前にする）
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

import yaml
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

STYLE_VERSION = 2  # 画像の型を変えたら上げる（全部作り直す）
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
        data = yaml.safe_load(m.group(1)) or {}
        if data.get("layout") != "article":
            continue
        yield rel, txt, m.group(1), data


def slug_of(data):
    p = str(data.get("permalink") or "").strip("/")
    p = re.sub(r"\.html?$", "", p)
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
    # 見出し: 1行に収まる大きさ（60以上）を探し、収まらなければ2行に分けて左右の長さをそろえる
    maxw = W - pad * 2
    tl = None
    for size in (84, 76, 68, 60):
        tf = f(BOLD, size)
        if d.textlength(title, font=tf) <= maxw:
            tl = [title]
            break
    if tl is None:
        for size in (72, 60):
            tf = f(BOLD, size)
            tl = wrap(d, title, tf, min(maxw, d.textlength(title, font=tf) / 2 + size))
            if len(tl) <= 2:
                break
    if len(tl) > 2:
        raise SystemExit(f"見出しが長すぎて画像に収まらない: {title}（「｜」で見出しと補足に分けてください）")
    sf = f(REG, 36)
    sl = wrap(d, sub, sf, maxw) if sub else []
    # 下の区切り線（y=510）より上に収める。補足が入りきらないときは行を減らし、それでも無理なら省く
    bottom = H - 140
    def end_y(n_sub):
        return 160 + int(size * 1.3) * len(tl) + (14 + 50 * n_sub if n_sub else 0)
    n_sub = min(len(sl), 2)
    while n_sub and end_y(n_sub) > bottom:
        n_sub -= 1
    if len(sl) > n_sub:
        print(f"  注意: 補足を{len(sl) - n_sub}行省いた: {title}")
    y = 160
    for line in tl:
        d.text((pad, y), line, font=tf, fill=INK)
        y += int(size * 1.3)
    for line in sl[:n_sub]:
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
    seen = {}
    for rel, txt, fm, data in pages():
        slug = slug_of(data)
        if not slug:
            print(f"::warning::{rel} に permalink がないので、シェア画像を作れない")
            continue
        if slug in seen:
            sys.exit(f"::error::シェア画像の名前が重なる: {seen[slug]} と {rel}（どちらも {slug}.png）")
        seen[slug] = rel
        img_rel = f"assets/images/og/{slug}.png"
        if isinstance(data.get("image"), dict):
            sys.exit(f"::error::{rel} の image: が複数行の書き方になっている（1行の image: /パス にしてください）")
        if data.get("og_photo") is True:
            # 第2段: 写真に差し替えた記事。image: に書いたパスの写真をそのまま使う
            img_rel = str(data.get("image") or "").lstrip("/")
            if not img_rel or not os.path.exists(os.path.join(ROOT, img_rel)):
                changed.append(f"{rel}（og_photo: true だが image: の写真がない）")
            continue
        full = str(data.get("title") or "")
        title, _, sub = full.partition("｜")
        title, sub = title.strip(), sub.strip()
        if not sub:
            # 「｜」がないページは description の最初の文を補足にする（文末の「。」は落とす）
            sub = re.split(r"(?<=。)", str(data.get("description") or ""))[0].rstrip("。")
        label = "保存方法ガイド" if "/storage/" in str(data.get("permalink")) else "まかないシェフの記事"
        if label == title:
            label = "まかないシェフの記事"
        key = hashlib.sha256(json.dumps([STYLE_VERSION, title, sub, label], ensure_ascii=False).encode()).hexdigest()[:16]
        new_manifest[slug] = key
        path = os.path.join(ROOT, img_rel)
        if manifest.get(slug) != key or not os.path.exists(path):
            changed.append(img_rel)
            if not check:
                open(path, "wb").write(render(title, sub, label))
        want = f"image: /{img_rel}"
        if re.search(r"^image:.*$", fm, re.M):
            new_fm = re.sub(r"^image:.*$", want, fm, count=1, flags=re.M)
        else:
            new_fm = fm + "\n" + want
        if new_fm != fm:
            changed.append(rel)
            if not check:
                open(os.path.join(ROOT, rel), "w", encoding="utf-8").write(txt.replace(fm, new_fm, 1))
    if new_manifest != manifest:
        changed.append("assets/images/og/manifest.json")
        if not check:
            with open(MANIFEST, "w", encoding="utf-8") as fp:
                json.dump(dict(sorted(new_manifest.items())), fp, ensure_ascii=False, indent=1)
                fp.write("\n")
    # 記事を消したり名前を変えたりして使われなくなった画像を消す
    for fn in sorted(os.listdir(OUT)):
        if fn.endswith(".png") and fn[:-4] not in new_manifest and fn[:-4] not in seen:
            changed.append(f"assets/images/og/{fn}（使われていない）")
            if not check:
                os.remove(os.path.join(OUT, fn))
    if changed:
        print(("作り直しが必要: " if check else "更新: ") + ", ".join(changed))
        if check:
            print("::error::シェア画像（scripts/make_og.py）を作り直していない記事があります。python scripts/make_og.py を実行してコミットしてください")
            sys.exit(1)
    else:
        print("シェア画像: 変更なし")


if __name__ == "__main__":
    main()
