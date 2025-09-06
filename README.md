# Matcha Contact Finder

このプロジェクトは、既存の抹茶営業リストを更新するためのシンプルなツールです。C列に店舗のホームページ URL がある前提で、そのサイトから以下の情報を取得し、シートに書き込みます。

- D列: Instagram のアカウント URL
- E列: 問い合わせメールアドレス
- F列: 問い合わせフォームへのリンク
- いずれも見つからない場合は G列に `なし` と記入

GitHub Action は以下の Google スプレッドシートを対象とし、A 列が空欄の行で処理を終了します。
https://docs.google.com/spreadsheets/d/1HU-GqN7sBcORIZrYEw4FkyfNmgDtXsO7CtDLVHEsldA/edit?gid=159511499#gid=159511499

開始行はコマンドライン引数 `--start-row` で指定するか、シートの `A1` に `Action`、`B1` に開始行番号を記載してください。指定がない場合は 2 行目から開始されます。終了行を限定したい場合は `--end-row` もしくは `C1` に終了行を指定できます。
デフォルトではシート名「抹茶営業リスト（カフェ）」を処理しますが、`--worksheet` 引数または GitHub Action の `worksheet-name` で別のシートを指定できます。

## 使い方

```bash
pip install -r requirements.txt  # 要 Python 3.11
# デフォルトのスプレッドシートを更新
python update_contact_info.py --start-row 2 --end-row 10 --worksheet 'Sheet1' --debug
# 別のファイルを処理したい場合はパスを指定
# python update_contact_info.py sample.xlsx --start-row 2 --end-row 10 --worksheet 'Sheet1' --debug
```
