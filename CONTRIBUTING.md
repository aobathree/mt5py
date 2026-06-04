# コントリビューションガイド

## 開発環境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install ruff
```

## コーディング規約

- `ruff check .` が通ること（設定は `pyproject.toml`）。
- 日本語コメント可。型ヒントを付けること。

## セキュリティ上の必須ルール

- **認証情報（ログイン番号・パスワード・サーバー名）を直書きしない。**
- 機密情報を含むファイル（`.env` など）をコミットしない。
- 新しい資格情報の読み取り経路を追加する場合も、パスワードは必ず実行時入力とする。

## プルリクエスト

1. ブランチを切る（例: `feature/list-positions`）。
2. 変更を加え、`ruff check .` と `python -m compileall list_orders.py mt5_oanda` を実行。
3. 内容を説明した PR を作成する。
