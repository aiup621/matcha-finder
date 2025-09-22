# Matcha Contact Finder

このプロジェクトは、既存の抹茶営業リストを更新するためのシンプルなツールです。C列に店舗のホームページ URL がある前提で、そのサイトから以下の情報を取得し、シートに書き込みます。

- D列: Instagram のアカウント URL
- E列: 問い合わせメールアドレス
- F列: 問い合わせフォームへのリンク
- いずれも見つからない場合は G列に `なし` と記入

GitHub Action は以下の Google スプレッドシートを対象とし、A 列が空欄の行で処理を終了します。
https://docs.google.com/spreadsheets/d/1HU-GqN7sBcORIZrYEw4FkyfNmgDtXsO7CtDLVHEsldA/edit?gid=159511499#gid=159511499

開始行はコマンドライン引数 `--start-row` で指定するか、シートの `A1` に `Action`、`B1` に開始行番号を記載してください。指定がない場合は 2 行目から開始されます。終了行を限定したい場合は `--end-row` もしくは `C1` に終了行を指定できますが、GitHub Actions でワークフローを実行する場合は開始行のみを指定し、A 列が空欄の行で自動的に処理が止まります。
デフォルトではシート名「抹茶営業リスト（カフェ）」を処理しますが、`--worksheet` 引数または GitHub Action の `worksheet-name` で別のシートを指定できます。

## 使い方

```bash
pip install -r requirements.txt  # 要 Python 3.11
# デフォルトのスプレッドシートを更新
python update_contact_info.py --start-row 2 --end-row 10 --worksheet 'Sheet1' --debug
# 別のファイルを処理したい場合はパスを指定
# python update_contact_info.py sample.xlsx --start-row 2 --end-row 10 --worksheet 'Sheet1' --debug
```

## Google API を使って直接シートを更新する

`update_contact_info_api.py` は Google Sheets API と Custom Search API を
利用してスプレッドシートに直接アクセスし、店舗名などからホーム
ページを検索して連絡先情報を記入します。事前にサービスアカウン
トの認証情報と Custom Search API の API キー／検索エンジン ID を
用意してください。

```bash
python update_contact_info_api.py \
    --spreadsheet-id <SPREADSHEET_ID> \
    --credentials service_account.json \
    --api-key <API_KEY> \
    --cx <SEARCH_ENGINE_ID>
```

## Post-processing

`update_contact_info_api.py` は書き込み完了後に E 列（メールアドレス）を
確認し、条件付き書式で色付けされた重複メールの行を自動で削除します。
背景色は Sheets API の `effectiveFormat` を参照して判定し、完全な白
（RGB 合計が 3.0 に近い値）以外であれば重複とみなします。環境によって
色が取得できない場合は、E 列の値をプログラム側で正規化・重複判定して
同じ行を削除候補にします。

環境変数で動作を調整できます（いずれもデフォルト値は `()` 内）。

- `CLEANUP_DUPLICATE_EMAIL_ROWS` (`true`): 後処理の有効／無効
- `EMAIL_COL_LETTER` (`E`): メールアドレスが入っている列
- `HEADER_ROWS` (`1`): ヘッダー行数。削除対象から除外されます。
- `DRY_RUN` (`false`): `true` を指定すると削除せず候補行だけをログ出力

重複行が見つかると Sheets API の `DeleteDimension` を使って連続する
行をまとめて削除します。DRY_RUN で動作確認したい場合は、最初に
`DRY_RUN=true` を設定し、ログに削除対象の行番号が表示されることを
確認してください。
