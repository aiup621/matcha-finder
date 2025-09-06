# Matcha Contact Finder

このプロジェクトは、既存の抹茶営業リストを更新するためのシンプルなツールです。C列に店舗のホームページ URL がある前提で、そのサイトから以下の情報を取得し、シートに書き込みます。

- D列: Instagram のアカウント URL
- E列: 問い合わせメールアドレス
- F列: 問い合わせフォームへのリンク
- いずれも見つからない場合は G列に `なし` と記入

開始行はコマンドライン引数 `--start-row` で指定するか、シートの `A1` に `Action`、`B1` に開始行番号を記載してください。終了行を限定したい場合は `--end-row` もしくは `C1` に終了行を指定できます。
デフォルトではシート名「抹茶営業リスト（カフェ）」を処理しますが、`--worksheet` 引数または GitHub Action の `worksheet-name` で別のシートを指定できます。

## 使い方

```bash
pip install -r requirements.txt  # 要 Python 3.11
python update_contact_info.py sample.xlsx --start-row 2 --end-row 10 --worksheet 'Sheet1' --debug
```

`--debug` を付けると処理中の URL や失敗したリクエストがログに出力され、デバッグに便利です。このコマンドは `sample.xlsx` の 2 行目から 10 行目まで処理します。シート内に `Action` 行を用意している場合、`--start-row` や `--end-row` は不要です。

## GitHub Actions での実行

このリポジトリは [GitHub Actions](https://docs.github.com/actions) でも実行できます。以下のような Workflow を用意すると、コミットや Pull Request 時に自動テストが走ります。

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest
```

独自の Excel ファイルを処理したい場合は、本リポジトリを Action として呼び出すこともできます。

```yaml
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: your-org/matcha-finder@v1
        with:
          sheet: path/to/file.xlsx
          start-row: 2
          end-row: 10
          worksheet-name: 抹茶営業リスト（カフェ）
          debug: true
```

`debug: true` を指定すると `--debug` オプション付きでスクリプトが実行されます。
