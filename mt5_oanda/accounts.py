"""OANDA 証券の口座・MT5 インスタンスに関する「非機密」の設定。

ここにはサーバー名・端末(インスタンス)のパス・口座エイリアスなど、
機密でない情報のみを置きます。
**パスワードやログイン番号などの機密情報は直書きしないでください。**
ログイン番号を控えておきたい場合のみ任意で `login` を設定できますが、
パスワードは常に起動時の対話入力で取得します。

このユーザー環境では、商品種別ごとに 3 つの MT5 インスタンスを
`C:\\MT5\\OANDA_FX` / `C:\\MT5\\OANDA_Commodity` / `C:\\MT5\\OANDA_Index`
に導入しています。
複数インスタンスがある場合、接続先を一意に決めるため `terminal_path` の
指定が必須です（未指定だと IPC timeout になりやすい）。
"""

from __future__ import annotations

from dataclasses import dataclass


# OANDA 証券（OANDA Japan）の代表的な MT5 サーバー名。
# 実際のサーバー名は MT5 端末のログイン画面に表示される名称に合わせてください。
OANDA_SERVERS: tuple[str, ...] = (
    "OANDA-Japan MT5 Live",
    "OANDA-Japan MT5 Demo",
    "OANDA-Japan Live",
    "OANDA-Japan Demo",
)


@dataclass(frozen=True)
class AccountProfile:
    """口座/インスタンスを識別するための非機密プロファイル。

    Attributes:
        alias:         人間に分かりやすい識別名（例: "fx"）。
        server:        MT5 サーバー名。
        terminal_path: その口座を開く MT5 インスタンスの terminal64.exe パス。
                       複数インスタンス環境では必須。
        login:         ログイン番号（任意）。控えとして保持してよいが、
                       指定が無ければ起動時に対話入力する。
        note:          メモ（任意）。
    """

    alias: str
    server: str
    terminal_path: str | None = None
    login: int | None = None
    note: str = ""


# 商品種別ごとの 3 インスタンス。パスは実環境に合わせて編集してください。
# （機密情報＝ログイン番号/パスワードはここに書かないこと）
KNOWN_ACCOUNTS: dict[str, AccountProfile] = {
    "fx": AccountProfile(
        alias="fx",
        server="OANDA-Japan MT5 Live",
        terminal_path=r"C:\MT5\OANDA_FX\terminal64.exe",
        note="FX 用インスタンス",
    ),
    "commodity": AccountProfile(
        alias="commodity",
        server="OANDA-Japan MT5 Live",
        terminal_path=r"C:\MT5\OANDA_Commodity\terminal64.exe",
        note="商品(Commodity) 用インスタンス",
    ),
    "index": AccountProfile(
        alias="index",
        server="OANDA-Japan MT5 Live",
        terminal_path=r"C:\MT5\OANDA_Index\terminal64.exe",
        note="指数(Index) 用インスタンス",
    ),
}
