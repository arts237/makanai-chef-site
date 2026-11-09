# まかないシェフ（サイト）

**https://makanai-chef.com/** のソースです。食材の冷凍・保存のしかたと、期限が切れてしまったときの考え方をまとめた記事と、賞味期限をDiscordのDMでお知らせするBot「まかないシェフ」の案内を載せています。

## サイトのおもなページ

- [トップ](https://makanai-chef.com/)
- [まかないシェフの始め方](https://makanai-chef.com/start/)
- [よくある質問](https://makanai-chef.com/faq/)
- [保存方法ガイド（記事の一覧）](https://makanai-chef.com/storage/)
- [食材別 保存のコツ早見表](https://makanai-chef.com/storage/foods/)

## 保存方法の記事

- [冷凍保存の基本｜失敗しないやり方と保存期間の目安](https://makanai-chef.com/storage/freezer-basics/)
- [食材別 保存のコツ早見表](https://makanai-chef.com/storage/foods/)
- [豚肉の冷凍保存](https://makanai-chef.com/storage/pork/)
- [鶏むね肉の冷凍保存](https://makanai-chef.com/storage/chicken-breast/)
- [ひき肉の冷凍保存](https://makanai-chef.com/storage/ground-meat/)
- [キャベツの冷凍保存](https://makanai-chef.com/storage/cabbage/)
- [ご飯の冷凍保存](https://makanai-chef.com/storage/rice/)
- [食パンの冷凍保存](https://makanai-chef.com/storage/bread/)
- [きのこの冷凍保存](https://makanai-chef.com/storage/mushroom/)
- [玉ねぎの冷凍保存](https://makanai-chef.com/storage/onion/)
- [鮭の切り身の冷凍保存](https://makanai-chef.com/storage/salmon/)
- [長ねぎの保存](https://makanai-chef.com/storage/negi/)
- [納豆の冷凍保存](https://makanai-chef.com/storage/natto/)
- [油揚げの冷凍保存](https://makanai-chef.com/storage/aburaage/)
- [ベーコンの冷凍保存](https://makanai-chef.com/storage/bacon/)
- [豆腐の冷凍保存](https://makanai-chef.com/storage/tofu/)

新しい記事は [フィード（/feed.xml）](https://makanai-chef.com/feed.xml) でも追えます。

---

以下は、このリポジトリを更新する人向けのメモです。

## 配信（2026-10-10〜 Cloudflare Workers）

- 本番: https://makanai-chef.com/ （Cloudflare Workers の静的配信。`main` にpushすると自動でビルド・公開）
- ビルドの設定（Cloudflare → Workers & Pages → makanai-chef-site → 設定 → ビルド）
  - ビルドコマンド: `bundle exec jekyll build` ／ デプロイコマンド: `npx wrangler deploy`
  - ビルド変数: `LANG=C.UTF-8`、`LC_ALL=C.UTF-8`（無いと、テーマのCSSに含まれる英数字以外の文字で止まる）
  - Rubyの版は `.ruby-version`（3.3.6）で固定
- 旧URL（arts237.github.io/makanai-chef-site）は `gh-pages-legacy` ブランチから配信（切り替え後は転送ページにする）

## 保存方法の記事を追加するとき（2026-09-29〜）

`storage/` に記事ファイルを1つ追加して push するだけで、次の場所に自動で反映されます（Botの再デプロイは不要です）。

- 保存方法ガイド（`/storage/`）の記事一覧、各記事の「食材別の冷凍保存」
- 買い足しガイド（`/shopping/`）の「今回の買い足し候補」＝Botの買い足しメッセージのリンク先

front matter に次の3項目を書いてください（買い足しガイドで食材と記事を結びつけるため）。

```yaml
order: 6                      # 一覧での並び順
food_keywords: ["鮭", "サーモン"]   # Botの食材名に含まれていたらこの記事を案内する語
food_tool: "冷凍用の保存袋"         # 候補欄に出す「使う道具」の名前
food_tool_q: "冷凍用 保存袋 ジッパー" # その道具のAmazon検索語
```

食材名が複数の記事に一致したときは、いちばん長く一致した語の記事を選びます（例:「豚ひき肉」は「豚」より「ひき肉」）。

## よく使う食材（記事なし）を追加するとき

`_data/foods.yml` に1件追加して push すると、「食材別 保存のコツ早見表」（`/storage/foods/`）と、買い足しガイドの候補欄（Botのリンク先）に自動で出ます。
`id`（英字）・`name`・`keywords`・必要なら `exclude`・`tip`（出典を確認した内容を言い換えて80字程度）・`tool`/`tool_q`（無ければ null）・`source_title`/`source_url` を書いてください。

## 記事を追加・更新したら

- 記事を追加したら、このREADMEの「保存方法の記事」にも1行足す
- 本文を変えたら front matter の `last_modified_at` を更新する（サイトマップの更新日になる）
- プルリクでは `article-check`（記事の検査・Jekyllのビルド・フィードの検査）が通ることを確かめてからマージする
