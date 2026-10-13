#!/usr/bin/env python3
"""記事の機械検査（自動化メディア構想 2-1 の②）。

対象: storage/ の下のページすべて。ただし LEGACY（人が書いた既存の記事。数値データへの
移し替えが終わったら外す）は除く。対象のページは ai_assisted: true（真偽値）と
layout: article が必須（付け忘れ・書き換えで検査を素通りさせないため）。

失敗すると終了コード1。GitHub Actions ではエラーを注釈として出す。
鍵（シークレット）は使わない。
"""
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GH = os.environ.get("GITHUB_ACTIONS") == "true"

LEGACY = {
    "storage/index.html", "storage/foods.html", "storage/freezer-basics.html",
    "storage/pork.html", "storage/chicken-breast.html", "storage/ground-meat.html",
    "storage/cabbage.html", "storage/rice.html",
}

# 本文・タイトル・説明文に直接書いてはいけない「数値＋単位」（数値は facts.yml から出す）
NUM = r"[0-9０-９][0-9０-９.,．]*"
UNIT_RE = re.compile(
    rf"(?:{NUM}\s*(?:[〜~～\-－]\s*{NUM})?\s*"
    rf"(?:日間|日|週間|週|か月|ヵ月|ヶ月|カ月|ケ月|か年|年|時間|分半|分|秒|℃|°C|度|W|Ｗ|ワット|cm|ｃｍ|センチ|mm|g|ｇ|グラム|ml|mL|ｍｌ)"
    rf"|[一二三四五六七八九十百数]+\s*(?:[〜~～]\s*[一二三四五六七八九十百]+)?\s*(?:日間|日|週間|か月|ヵ月|ヶ月|カ月|ケ月|時間|分|センチ|グラム)"
    rf"|半日|半年|半月|ひと月|ひと晩|一晩)"
)

# 禁止語（2026-09-30の表現の決まり＋構想3章）
FORBIDDEN = [
    "お得", "最安", "絶対", "必ず長持ち", "期限が延びる", "期限を延ばす", "期限が伸びる",
    "毎朝", "すべて無料", "完全無料", "食品ロスがなくなる", "食品ロスをなくす", "節約できる",
    "安全です", "食べても大丈夫", "医師", "管理栄養士", "専門家が",
]

REQUIRED_FM = ["title", "short_title", "description", "permalink", "date", "food_id",
               "category_name", "category_url", "order"]
REQUIRED_BODY = [
    ('class="a-answer"', "結論ボックス（a-answer）"),
    ("{% include storage-table.html", "保存期間の表（storage-table.html）"),
    ("{% include sources.html", "出典の一覧（sources.html）"),
    ("{% include bot-box.html", "Botの紹介（bot-box.html。固定の部品）"),
    ("{% include related-storage.html", "関連記事（related-storage.html）"),
    ('class="a-unique"', "その記事にしかない部分（a-unique。使い切りのコツか自前の手順写真）"),
]

errors = []


def err(path, msg, line=None):
    rel = os.path.relpath(path, ROOT)
    errors.append(f"{rel}: {msg}")
    if GH:
        loc = f"file={rel}" + (f",line={line}" if line else "")
        print(f"::error {loc}::{msg}")
    else:
        print(f"NG {rel}{':' + str(line) if line else ''}: {msg}")


def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


facts = load(os.path.join(ROOT, "_data/facts.yml")) or []
sources = load(os.path.join(ROOT, "_data/sources.yml")) or {}
fact_ids = {}
for i, f in enumerate(facts):
    fid = f.get("id")
    p = os.path.join(ROOT, "_data/facts.yml")
    if not fid:
        err(p, f"{i + 1}件目に id がない")
        continue
    if fid in fact_ids:
        err(p, f"id が重複: {fid}")
    fact_ids[fid] = f
    for k in ("food", "value", "source", "quote"):
        if not f.get(k):
            err(p, f"{fid}: {k} がない（数値には出典と原文の引用が必須）")
    if f.get("source") and f["source"] not in sources:
        err(p, f"{fid}: 出典 {f['source']} が sources.yml にない")
    if f.get("value") and f.get("quote"):
        for d in re.findall(r"[0-9]+", str(f["value"])):
            if d not in str(f["quote"]):
                err(p, f"{fid}: value の数字 {d} が quote（出典の原文）に無い")
    if f.get("kind") == "period" and not f.get("label"):
        err(p, f"{fid}: 表に出す行（kind: period）に label がない")
for k, s in sources.items():
    p = os.path.join(ROOT, "_data/sources.yml")
    for need in ("short", "title", "url", "checked"):
        if not (s or {}).get(need):
            err(p, f"{k}: {need} がない")


def strip_markup(text):
    text = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", " ", text, flags=re.S)
    text = re.sub(r"\{%.*?%\}", " ", text, flags=re.S)
    text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


pages = []
for path in sorted(glob.glob(os.path.join(ROOT, "**/*.html"), recursive=True) +
                   glob.glob(os.path.join(ROOT, "**/*.htm"), recursive=True) +
                   glob.glob(os.path.join(ROOT, "**/*.md"), recursive=True)):
    rel = os.path.relpath(path, ROOT)
    if rel.startswith(("_site", "_includes", "_layouts", "vendor", "node_modules", ".")):
        continue
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, flags=re.S)
    if not m:
        continue
    fm = yaml.safe_load(m.group(1)) or {}
    pages.append((path, fm, m.group(2), m.group(1).count("\n") + 3))

# URL と食材の重なり（全ページ対象）
seen_link, seen_food = {}, {}
for path, fm, body, off in pages:
    pl = fm.get("permalink")
    if pl:
        if pl in seen_link:
            err(path, f"permalink が {os.path.relpath(seen_link[pl], ROOT)} と重複: {pl}")
        seen_link[pl] = path
    fid = fm.get("food_id")
    if fid:
        if fid in seen_food:
            err(path, f"food_id {fid} の記事が既にある: {os.path.relpath(seen_food[fid], ROOT)}（1食材×1目的＝1ページ）")
        seen_food[fid] = path

amazon_q = set(load(os.path.join(ROOT, "_data/amazon_queries.yml")) or [])
targets = []
for p, fm, b, off in pages:
    rel = os.path.relpath(p, ROOT)
    if rel.startswith("storage/") and rel not in LEGACY:
        targets.append((p, fm, b, off))
    elif fm.get("ai_assisted"):
        err(p, "ai_assisted は storage/ の新しい記事にだけ付ける（ほかの場所では検査の対象外になる）")
for path, fm, body, off in targets:
    if fm.get("ai_assisted") is not True:
        err(path, "ai_assisted: true（真偽値）がない。AI利用の表示が出ず、型の検査とも食い違う")
    if fm.get("layout") != "article":
        err(path, "layout: article にする（AI利用の表示とPR表示はこのレイアウトが出す）")
    for k in REQUIRED_FM:
        if fm.get(k) in (None, ""):
            err(path, f"front matter に {k} がない")
    if fm.get("category_url") != "/storage/":
        err(path, "category_url は /storage/ にする")
    for needle, name in REQUIRED_BODY:
        if needle not in body:
            err(path, f"必須の部品がない: {name}")
    food = fm.get("food_id")
    if food and not any(f.get("food") == food and f.get("kind") == "period" for f in facts):
        err(path, f"facts.yml に food: {food} の保存期間（kind: period）がない")
    for tag in re.findall(r"\{%-?\s*include\s+(?:storage-table|sources)\.html\s+food=\"([^\"]+)\"", body):
        if tag != food:
            err(path, f"部品の food=\"{tag}\" が front matter の food_id（{food}）と違う")
    for fid in re.findall(r"\{%-?\s*include\s+fact\.html\s+id=\"([^\"]+)\"", body):
        if fid not in fact_ids:
            err(path, f"facts.yml にない id を参照: {fid}")
    for ex in re.findall(r"\{%-?\s*include\s+sources\.html[^%]*extra=\"([^\"]+)\"", body):
        for k in ex.split(","):
            if k.strip() not in sources:
                err(path, f"sources.yml にない出典: {k.strip()}")

    # Amazon: 部品（amazon-link.html）経由だけ。PR表示とアソシエイトの表記
    if re.search(r"amazon\.(co\.jp|com)|amzn\.", body):
        err(path, "Amazonのリンクを直接書いている（amazon-link.html を使う）")
    links = re.findall(r"\{%-?\s*include\s+amazon-link\.html([^%]*)-?%\}", body)
    if links:
        if fm.get("has_pr") is not True:
            err(path, "Amazonのリンクがあるのに has_pr: true がない")
        if not re.search(r"\{%-?\s*include\s+amazon-note\.html", body):
            err(path, "Amazonのリンクがあるのに amazon-note.html（アソシエイトの表記）がない")
        if len(links) > 4:
            err(path, "Amazonのリンクが多すぎる（4か所まで）")
        for args in links:
            q = re.search(r'q="([^"]*)"', args)
            if not q or q.group(1) not in amazon_q:
                err(path, f"Amazonの検索語が対応表（_data/amazon_queries.yml）にない: {q.group(1) if q else '(なし)'}")
    for k in ("food_tool_q",):
        if fm.get(k) and fm[k] not in amazon_q:
            err(path, f"{k} が対応表（_data/amazon_queries.yml）にない: {fm[k]}")

    # 数値＋単位の直書きと禁止語（本文・タイトル・説明文）
    text_fields = [("title", fm.get("title") or ""), ("short_title", fm.get("short_title") or ""),
                   ("description", fm.get("description") or "")]
    for name, val in text_fields:
        for mm in UNIT_RE.finditer(val):
            err(path, f"{name} に数値＋単位を直接書いている: 「{mm.group(0)}」（数値は本文で fact.html から出す）")
        for w in FORBIDDEN:
            if w in val:
                err(path, f"{name} に禁止語: 「{w}」")
    for i, line in enumerate(body.split("\n")):
        scan = re.sub(r'\bq="[^"]*"', " ", line)  # Amazonの検索語は対応表で別に確認する
        hidden = " ".join(re.findall(r'"([^"]*)"', scan) + re.findall(r"\{\{(.*?)\}\}", scan))
        hidden = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", " ", hidden)
        plain = strip_markup(line) + " " + hidden
        for mm in UNIT_RE.finditer(plain):
            err(path, f"本文に数値＋単位を直接書いている: 「{mm.group(0)}」（fact.html で出す）", off + i)
        for w in FORBIDDEN:
            if w in plain:
                err(path, f"本文に禁止語: 「{w}」", off + i)

print(f"検査した記事: {len(targets)}件 / エラー: {len(errors)}件")
sys.exit(1 if errors else 0)
