# Matcha Contact Finder

このプロジェクトは、既存の抹茶営業リストを更新するためのシンプルなツールです。C列に店舗のホームページ URL がある前提で、そのサイトから以下の情報を取得し、シートに書き込みます。

- D列: Instagram のアカウント URL
- E列: 問い合わせメールアドレス
- F列: 問い合わせフォームへのリンク
- いずれも見つからない場合は G列に `なし` と記入

開始行はコマンドライン引数 `--start-row` で指定するか、シートの `A1` に `Action`、`B1` に開始行番号を記載してください。

## 使い方

```bash
pip install -r requirements.txt
python update_contact_info.py sample.xlsx --start-row 2
```

このコマンドは `sample.xlsx` の 2 行目から処理を開始します。シート内に `Action` 行を用意している場合、`--start-row` は不要です。
