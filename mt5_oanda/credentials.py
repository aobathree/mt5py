"""起動時に認証情報を対話的に取得するモジュール。

設計方針:
    - ログイン番号 / パスワード / サーバー名は **ソースに直書きしない**。
    - 変数(dataclass)として保持し、プログラム起動時にユーザーへ問い合わせる。
    - パスワードは getpass を用いて画面に表示せずに入力させる。
    - 非機密のデフォルト値（ログイン番号・サーバー名・口座エイリアス）は
      環境変数 / .env から補完できるが、パスワードは決して読み込まない。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from getpass import getpass

from .accounts import KNOWN_ACCOUNTS, OANDA_SERVERS, AccountProfile

try:  # .env からの非機密デフォルト読み込みは任意機能
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv 未インストールでも動作する
    pass


@dataclass
class Credentials:
    """MT5 ログインに必要な認証情報 + 接続先インスタンス情報。

    パスワードはメモリ上にのみ保持し、ログ出力や repr で露出しないようにする。
    terminal_path は機密ではないが、選択した口座(インスタンス)と対応するため
    ここに同梱しておく。
    """

    login: int
    password: str
    server: str
    terminal_path: str | None = None

    def __repr__(self) -> str:  # パスワードを伏せる
        return (
            f"Credentials(login={self.login}, server={self.server!r}, "
            f"terminal_path={self.terminal_path!r}, password=***)"
        )


def _select_account_profile() -> AccountProfile | None:
    """登録済み口座から 1 つを選ばせる（任意）。未登録なら None を返す。"""
    if not KNOWN_ACCOUNTS:
        return None

    default_alias = os.getenv("MT5_DEFAULT_ACCOUNT", "").strip()

    aliases = list(KNOWN_ACCOUNTS.keys())
    print("利用可能な口座プロファイル:")
    for i, alias in enumerate(aliases, start=1):
        prof = KNOWN_ACCOUNTS[alias]
        note = f" - {prof.note}" if prof.note else ""
        print(f"  [{i}] {alias} (server={prof.server}){note}")
    print("  [0] 登録リストを使わず手入力する")

    prompt = "口座を番号で選択してください"
    if default_alias in KNOWN_ACCOUNTS:
        prompt += f" [既定: {default_alias}]"
    prompt += ": "

    raw = input(prompt).strip()
    if not raw and default_alias in KNOWN_ACCOUNTS:
        return KNOWN_ACCOUNTS[default_alias]
    if not raw or raw == "0":
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(aliases):
        return KNOWN_ACCOUNTS[aliases[int(raw) - 1]]
    # エイリアス名での直接指定にも対応
    if raw in KNOWN_ACCOUNTS:
        return KNOWN_ACCOUNTS[raw]

    print("  入力が不正です。手入力に切り替えます。")
    return None


def _prompt_login(default: int | None) -> int:
    env_default = os.getenv("MT5_LOGIN", "").strip()
    if default is None and env_default.isdigit():
        default = int(env_default)

    while True:
        suffix = f" [既定: {default}]" if default is not None else ""
        raw = input(f"ログイン番号(口座番号){suffix}: ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit():
            return int(raw)
        print("  数字のみで入力してください。")


def _prompt_server(default: str | None) -> str:
    if not default:
        default = os.getenv("MT5_SERVER", "").strip() or None

    print("サーバー名の候補:")
    for i, srv in enumerate(OANDA_SERVERS, start=1):
        print(f"  [{i}] {srv}")
    print("  [0] 手入力する")

    suffix = f" [既定: {default}]" if default else ""
    raw = input(f"サーバーを番号で選択、または名称を入力{suffix}: ").strip()

    if not raw and default:
        return default
    if raw.isdigit():
        idx = int(raw)
        if idx == 0:
            return input("サーバー名を入力してください: ").strip()
        if 1 <= idx <= len(OANDA_SERVERS):
            return OANDA_SERVERS[idx - 1]
    # 数字以外はそのままサーバー名として扱う
    return raw


def _prompt_password() -> str:
    while True:
        pw = getpass("パスワード(入力は表示されません): ")
        if pw:
            return pw
        print("  パスワードが空です。再入力してください。")


def prompt_credentials() -> Credentials:
    """起動時にユーザーへ問い合わせて Credentials を生成する。

    フロー:
        1. 登録済み口座プロファイルを選ばせる（任意）。
        2. ログイン番号・サーバー名を入力（プロファイル/環境変数で補完可）。
        3. パスワードを getpass で安全に入力。
    """
    profile = _select_account_profile()

    default_login = profile.login if profile else None
    default_server = profile.server if profile else None
    terminal_path = profile.terminal_path if profile else None

    login = _prompt_login(default_login)
    server = _prompt_server(default_server)
    password = _prompt_password()

    return Credentials(
        login=login,
        password=password,
        server=server,
        terminal_path=terminal_path,
    )
