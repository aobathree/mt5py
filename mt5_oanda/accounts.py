"""OANDA 証券の口座に関する「非機密」の設定（サーバー名・口座エイリアス）。

ここにはログイン番号やサーバー名など、機密でない情報のみを置きます。
**パスワードやログイン番号などの機密情報は直書きしないでください。**
ログイン番号を控えておきたい場合のみ任意で `login` を設定できますが、
パスワードは常に起動時の対話入力で取得します。
"""

from __future__ import annotations

from dataclasses import dataclass, field


# OANDA 証券（OANDA Japan）の代表的な MT5 サーバー名。
# 実際のサーバー名は MT5 端末のログイン画面に表示される名称に合わせてください。
OANDA_SERVERS: tuple[str, ...] = (
    "OANDA-Japan Live",
    "OANDA-Japan Demo",
    "OANDA-v20 Live-1",
    "OANDA-v20 Practice-1",
)


@dataclass(frozen=True)
class AccountProfile:
    """口座を識別するための非機密プロファイル。

    Attributes:
        alias:  人間に分かりやすい識別名（例: "live1"）。
        server: MT5 サーバー名。
        login:  ログイン番号（任意）。控えとして保持してよいが、
                指定が無ければ起動時に対話入力する。
        note:   メモ（任意）。
    """

    alias: str
    server: str
    login: int | None = None
    note: str = ""


# 複数口座を切り替えやすくするための任意の登録リスト。
# 必要に応じて自由に編集してください（機密情報は書かないこと）。
KNOWN_ACCOUNTS: dict[str, AccountProfile] = {
    "live1": AccountProfile(alias="live1", server="OANDA-Japan Live", note="本番口座 1"),
    "live2": AccountProfile(alias="live2", server="OANDA-Japan Live", note="本番口座 2"),
    "demo1": AccountProfile(alias="demo1", server="OANDA-Japan Demo", note="デモ口座 1"),
}
