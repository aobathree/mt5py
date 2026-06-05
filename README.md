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

### 東京仲値(9:55 JST)の値動き検証・記録

仲値前後のドル円の値動き（仲値に向けた上昇・仲値後の反落）を、ヒストリカル M1 データから日次で計測し、**全体 / 五十日(ごとおび) / それ以外**に分けて統計表示します。`--csv` で明細を保存できます。

```powershell
# 直近90日を分析
python analyze_tokyo_fix.py

# 期間や計測時刻を指定し、明細を CSV 保存
python analyze_tokyo_fix.py --days 120 --pre 09:00 --fix 09:55 --post 10:30 --csv nakane.csv
```

計測内容:

- **run_up**: 仲値前(既定 09:00) → 仲値(09:55) の変化[pips]。プラスが多いほど「仲値に向けて上昇」。
- **reversal**: 仲値(09:55) → 仲値後(既定 10:30) の変化[pips]。マイナスが多いほど「仲値後に反落」。
- **五十日(ごとおび)**: 5・10・15・20・25・末日（土日なら直前の平日へ繰上げ）を自動判定。

> 時刻は日本時間(JST)で扱います。ブローカーのサーバー時刻オフセットはライブティックから自動推定します（`--tz-offset-hours` で明示指定も可能）。夏時間切替を跨ぐ期間では 1 時間ずれる可能性があるため、必要に応じてオフセットを指定してください。
>
> ⚠️ これは**検証・記録用ツール**であり、将来の値動きや利益を保証するものではありません。

起動すると、登録済み口座の選択 → ログイン番号 → サーバー名 → パスワードの順に入力を求められます。

```
=== OANDA (MetaTrader 5) オープン注文一覧 ===

利用可能な口座プロファイル:
  [1] fx (server=OANDA-Japan MT5 Live) - FX 用インスタンス
  [2] commodity (server=OANDA-Japan MT5 Live) - 商品(Commodity) 用インスタンス
  [3] index (server=OANDA-Japan MT5 Live) - 指数(Index) 用インスタンス
  [0] 登録リストを使わず手入力する
口座を番号で選択してください: 1
ログイン番号(口座番号): 900175195
サーバーを番号で選択、または名称を入力 [既定: OANDA-Japan MT5 Live]:
パスワード(入力は表示されません):
```

## 複数口座 / 複数インスタンスの登録

このプロジェクトは、商品種別ごとに複数の MT5 インスタンスを使う構成を前提にしています。`mt5_oanda/accounts.py` の `KNOWN_ACCOUNTS` を編集してください。**サーバー名・端末パス・エイリアスなど非機密情報のみ**を記載します（ログイン番号/パスワードは書かない）。

```python
KNOWN_ACCOUNTS = {
    "fx": AccountProfile(
        alias="fx", server="OANDA-Japan Live",
        terminal_path=r"C:\MT5\OANDA_FX\terminal64.exe", note="FX 用インスタンス",
    ),
    "commodity": AccountProfile(
        alias="commodity", server="OANDA-Japan Live",
        terminal_path=r"C:\MT5\OANDA_Commodity\terminal64.exe", note="商品用インスタンス",
    ),
    "index": AccountProfile(
        alias="index", server="OANDA-Japan Live",
        terminal_path=r"C:\MT5\OANDA_Index\terminal64.exe", note="指数用インスタンス",
    ),
}
```

> **重要:** MT5 インスタンスが複数ある場合、接続先を一意に決めるため `terminal_path` の指定が必須です。未指定だと Python API がどの端末に繋ぐか定まらず、`IPC timeout` になりがちです。口座を選択すると、そのプロファイルの `terminal_path` が自動的に接続先として使われます。
>
> サーバー名は、ご利用の MT5 端末のログイン画面に表示される名称に合わせてください（例: `OANDA-Japan Live`）。

## プロジェクト構成

```
mt5py/
├── list_orders.py          # オープン注文/ポジション一覧
├── analyze_tokyo_fix.py    # 東京仲値(9:55)の値動き検証・記録
├── mt5_oanda/
│   ├── __init__.py
│   ├── accounts.py         # 非機密の口座プロファイル / サーバー名 / 端末パス
│   ├── credentials.py      # 起動時の認証情報プロンプト（getpass）
│   ├── connection.py       # MT5 接続/ログイン/切断（context manager）
│   ├── orders.py           # 注文・ポジション取得
│   ├── display.py          # 全角対応のコンソール表整形
│   ├── market_data.py      # M1取得・JST変換・サーバー時刻オフセット・pip計算
│   └── tokyo_fix.py        # 仲値ウィンドウ集計・五十日判定・統計
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## トラブルシューティング

### `MT5 の初期化に失敗しました (code=-10005): IPC timeout`

Python API が MT5 端末(`terminal64.exe`)と通信できないときに発生します。ログイン以前の段階のエラーです。

本ツールは「**起動・ログイン済みの端末にアタッチする**」方式で接続します。複数インスタンス環境では、接続先の指定と起動状態が特に重要です。次を順に確認してください。

1. **接続したい『その』インスタンスを手動で起動する。**
   - 例: エクスプローラで `C:\MT5\OANDA_FX\terminal64.exe` をダブルクリック。
   - 別フォルダ/別アプリ版の MT5 を開いても接続先にはなりません（パスが一致した端末のみ）。
2. その端末で対象口座に**ログイン**し、画面右下の接続状態が**緑(接続済み)**であること。
3. `ツール > オプション > エキスパートアドバイザ` で **「アルゴリズム取引を許可する」** を有効化。
4. **同じ口座を別の MT5 で同時に開かない。** 二重ログインはサーバーに切断されます（Journal に `disconnected` と出ます）。接続先以外の MT5（Windows アプリ版など）は閉じてください。
5. **Python と端末のビット数(64bit)を一致**させる。

パスを明示指定したい場合:

```powershell
python list_orders.py --terminal-path "C:\MT5\OANDA_FX\terminal64.exe"
```

### `ログインに失敗しました`

ログイン番号・パスワード・**サーバー名**を確認してください。サーバー名は MT5 端末のログイン画面に表示される正確な名称（OANDA 証券では **`OANDA-Japan MT5 Live`**）に一致している必要があります。異なる場合は `mt5_oanda/accounts.py` の `OANDA_SERVERS` を実際の名称に修正してください。

なお、対象端末が既に目的の口座にログイン済みであれば、本ツールは再ログインを行わずにそのままアタッチします（入力したパスワードは使用されません）。

## セキュリティに関する注意

- ログイン番号・パスワードを**コードや設定ファイルに直書きしない**でください。
- `.env`・`*.secret`・`credentials.json` などは `.gitignore` 済みです。
- パスワードはメモリ上にのみ保持し、`Credentials` の `repr` でもマスクされます。

## 免責事項

本ソフトウェアは現状有姿で提供されます。実際の取引・発注操作はご自身の責任で行ってください。まずはデモ口座での動作確認を推奨します。

## ライセンス

[MIT License](LICENSE)
