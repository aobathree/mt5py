"""MetaTrader 5 端末への接続・ログイン・切断を管理するモジュール。

MetaTrader5 パッケージは Windows 専用です。端末(terminal64.exe)が
インストール済みで、Python からの自動売買(アルゴリズム取引)が許可されている
必要があります。
"""

from __future__ import annotations

import os
from types import TracebackType

from .credentials import Credentials

try:
    import MetaTrader5 as mt5
except ImportError:  # 実行時に分かりやすいメッセージを出す
    mt5 = None  # type: ignore[assignment]


class MT5Error(RuntimeError):
    """MT5 の初期化・ログインに失敗した場合に送出する例外。"""


def _ensure_package() -> None:
    if mt5 is None:
        raise MT5Error(
            "MetaTrader5 パッケージが見つかりません。\n"
            "  pip install MetaTrader5\n"
            "を実行してください（Windows 専用）。"
        )


class MT5Connection:
    """MT5 への接続を管理する context manager。

    使い方:
        with MT5Connection(credentials) as conn:
            orders = mt5.orders_get()

    終了時に必ず ``mt5.shutdown()`` を呼び出します。
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        terminal_path: str | None = None,
        timeout_ms: int = 60_000,
    ) -> None:
        self.credentials = credentials
        # 端末パスは引数 > 環境変数 の優先順位で解決（未指定なら自動検出）
        self.terminal_path = terminal_path or os.getenv("MT5_TERMINAL_PATH") or None
        self.timeout_ms = timeout_ms
        self._connected = False

    def connect(self) -> "MT5Connection":
        _ensure_package()

        init_kwargs: dict[str, object] = {
            "login": self.credentials.login,
            "password": self.credentials.password,
            "server": self.credentials.server,
            "timeout": self.timeout_ms,
        }
        if self.terminal_path:
            init_kwargs["path"] = self.terminal_path

        # initialize() で端末起動とログインをまとめて試みる
        if not mt5.initialize(**init_kwargs):
            code, msg = mt5.last_error()
            raise MT5Error(f"MT5 の初期化に失敗しました (code={code}): {msg}")

        # 念のため明示的に login も行い、対象口座へ確実に切り替える
        if not mt5.login(
            self.credentials.login,
            password=self.credentials.password,
            server=self.credentials.server,
        ):
            code, msg = mt5.last_error()
            mt5.shutdown()
            raise MT5Error(
                f"ログインに失敗しました (login={self.credentials.login}, "
                f"server={self.credentials.server}, code={code}): {msg}"
            )

        self._connected = True
        return self

    def account_summary(self) -> dict[str, object]:
        """ログイン中の口座情報を辞書で返す。"""
        _ensure_package()
        info = mt5.account_info()
        if info is None:
            code, msg = mt5.last_error()
            raise MT5Error(f"口座情報を取得できません (code={code}): {msg}")
        return info._asdict()

    def shutdown(self) -> None:
        if mt5 is not None and self._connected:
            mt5.shutdown()
            self._connected = False

    def __enter__(self) -> "MT5Connection":
        return self.connect()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown()
