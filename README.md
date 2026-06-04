# mt5-oanda

OANDA 証券の口座に [MetaTrader 5 (MT5) Python パッケージ](https://www.mql5.com/en/docs/python_metatrader5) 経由でアクセスし、各種操作を行うためのツール群です。

最初のプログラムとして、**オープン中の注文(待機注文)および保有ポジションを一覧表示**するスクリプトを提供します。

## 特徴

- **認証情報をソースに直書きしない。** ログイン番号(ユーザーID)・パスワード・サーバー名は変数として扱い、**プログラム起動時に対話入力**します。パスワードは `getpass` により画面に表示されません。
- **複数口座に対応。** よく使う口座を `mt5_oanda/accounts.py` にエイリアスとして登録しておき、起動時に選択できます（機密情報は登録しません）。
- 非機密のデフォルト値（ログイン番号・サーバー名）は任意で `.env` から補完できます。**パスワードは `.env` からは決して読み込みません。**

## 動作環境

- **Windows のみ**（`MetaTrader5` パッケージは Windows 専用です）。
- Python 3.10 以上。
- OANDA 証券の MetaTrader 5 端末（`terminal64.exe`）がインストール済みであること。
- MT5 端末側で「アルゴリズム取引（自動売買）」が有効であること。

## セットアップ

```powershell
# 1. 仮想環境（任意）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 依存パッケージのインストール
pip install -r requirements.txt

# 3. （任意）非機密デフォルト値の設定
copy .env.example .env
# .env を編集（パスワードは書かない）
```

## 使い方

```powershell
# オープン注文 + 保有ポジションを一覧表示
python list_orders.py

# 銘柄でフィルタ
python list_orders.py --symbol USDJPY

# 待機注文のみ / ポジションのみ
python list_orders.py --orders-only
python list_orders.py --positions-only
```

起動すると、登録済み口座の選択 → ログイン番号 → サーバー名 → パスワードの順に入力を求められます。

```
=== OANDA (MetaTrader 5) オープン注文一覧 ===

利用可能な口座プロファイル:
  [1] live1 (server=OANDA-Japan Live) - 本番口座 1
  [2] live2 (server=OANDA-Japan Live) - 本番口座 2
  [3] demo1 (server=OANDA-Japan Demo) - デモ口座 1
  [0] 登録リストを使わず手入力する
口座を番号で選択してください: 3
ログイン番号(口座番号): 1234567
サーバーを番号で選択、または名称を入力 [既定: OANDA-Japan Demo]:
パスワード(入力は表示されません):
```

## 複数口座の登録

`mt5_oanda/accounts.py` の `KNOWN_ACCOUNTS` を編集します。**サーバー名やエイリアスなど非機密情報のみ**を記載してください。

```python
KNOWN_ACCOUNTS = {
    "live1": AccountProfile(alias="live1", server="OANDA-Japan Live", note="本番口座 1"),
    "demo1": AccountProfile(alias="demo1", server="OANDA-Japan Demo", note="デモ口座 1"),
}
```

> サーバー名は、ご利用の MT5 端末のログイン画面に表示される名称に合わせてください（例: `OANDA-Japan Live` / `OANDA-Japan Demo`）。

## プロジェクト構成

```
mt5py/
├── list_orders.py          # エントリーポイント（オープン注文一覧）
├── mt5_oanda/
│   ├── __init__.py
│   ├── accounts.py         # 非機密の口座プロファイル / サーバー名
│   ├── credentials.py      # 起動時の認証情報プロンプト（getpass）
│   ├── connection.py       # MT5 接続/ログイン/切断（context manager）
│   └── orders.py           # 注文・ポジション取得
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## セキュリティに関する注意

- ログイン番号・パスワードを**コードや設定ファイルに直書きしない**でください。
- `.env`・`*.secret`・`credentials.json` などは `.gitignore` 済みです。
- パスワードはメモリ上にのみ保持し、`Credentials` の `repr` でもマスクされます。

## 免責事項

本ソフトウェアは現状有姿で提供されます。実際の取引・発注操作はご自身の責任で行ってください。まずはデモ口座での動作確認を推奨します。

## ライセンス

[MIT License](LICENSE)
