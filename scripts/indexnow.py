#!/usr/bin/env python3
"""main に入った変更のうち、公開ページのURLを IndexNow（Bing など）へ知らせる（M-006）。

- 変わったファイルの front matter の permalink を集める（記事・固定ページ。sitemap: false は除く）
- Cloudflare の本番ビルド（約15分）が終わってから送るため、各URLの公開ページに
  そのコミットの last_modified_at が出る（sitemap.xml の <lastmod>）まで待つ。最大40分
- キーは公開ファイル（リポジトリ直下の <key>.txt）。秘密情報は使わない
Google は IndexNow に対応していない。
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import yaml

HOST = "makanai-chef.com"
BASE = f"https://{HOST}"
WAIT_MAX = 40 * 60
STEP = 60


def key():
    for p in glob.glob("*.txt"):
        name = os.path.splitext(os.path.basename(p))[0]
        if re.fullmatch(r"[0-9a-f]{32}", name) and open(p).read().strip() == name:
            return name
    sys.exit("IndexNow のキーファイルが見つからない")


def changed_files(before, after):
    if not before or set(before) == {"0"}:
        cmd = ["git", "show", "--name-only", "--format=", after]
    else:
        cmd = ["git", "diff", "--name-only", before, after]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l]


def urls_for(files):
    urls = {}
    for f in files:
        if not f.endswith((".html", ".md")) or f.startswith(("_", ".", "scripts/")) or not os.path.exists(f):
            continue
        m = re.match(r"^---\n(.*?)\n---\n", open(f, encoding="utf-8").read(), flags=re.S)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        if fm.get("sitemap") is False or not fm.get("permalink"):
            continue
        lm = fm.get("last_modified_at")
        urls[BASE + fm["permalink"]] = str(lm)[:10] if lm else None
    return urls


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "makanai-chef-indexnow", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def live(urls):
    """sitemap.xml の lastmod が、変更後の last_modified_at になったURL（無いURLは200で返れば公開とみなす）"""
    ok = []
    try:
        sm = fetch(f"{BASE}/sitemap.xml?t={int(time.time())}")
    except Exception as e:  # noqa: BLE001
        print(f"sitemap.xml を読めない: {e}")
        sm = ""
    for u, lm in urls.items():
        if lm:
            m = re.search(re.escape(u) + r"</loc>\s*<lastmod>([0-9-]{10})", sm)
            if m and m.group(1) >= lm:
                ok.append(u)
        else:
            try:
                fetch(u)
                ok.append(u)
            except Exception:  # noqa: BLE001
                pass
    return ok


def main():
    before, after = os.environ.get("BEFORE", ""), os.environ.get("AFTER", "HEAD")
    urls = urls_for(changed_files(before, after))
    if not urls:
        print("知らせるURLなし")
        return
    print("対象:", ", ".join(urls))
    k = key()
    waited, ready = 0, []
    while True:
        ready = live(urls)
        if len(ready) == len(urls) or waited >= WAIT_MAX:
            break
        time.sleep(STEP)
        waited += STEP
    if not ready:
        print("::warning::本番に反映されたURLが確認できなかったため、送らなかった")
        return
    if len(ready) < len(urls):
        print("::warning::反映を確認できなかったURL:", ", ".join(sorted(set(urls) - set(ready))))
    body = json.dumps({"host": HOST, "key": k, "keyLocation": f"{BASE}/{k}.txt", "urlList": ready}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: HTTP {r.status} / {len(ready)}件送信:", ", ".join(ready))
    except urllib.error.HTTPError as e:
        print(f"::error::IndexNow: HTTP {e.code} {e.read()[:300]!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
