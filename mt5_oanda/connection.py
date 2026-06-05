"""MetaTrader 5 端末への接続・ログイン・切断を管理するモジュール。

MetaTrader5 パッケージは Windows 専用です。端末(terminal64.exe)が
インストール済みで、Python からの自動売買(アルゴリズム取引)が許可されている
必要があります。

接続方針(IPC timeout 対策):
    1. まず ``mt5.initialize()`` で端末を起動/接続し、IPC 経路を確立する。
       - 端末パスが分かる場合は ``path`` を渡す（自動検出も試みる）。
       - 失敗時は数回リトライする。
    2. IPC 確立後に ``mt5.login()`` で対象口座へログインする。
"""

from __future__ import annotations

import os
import time
from glob import glob
from types import TracebackType

from .credentials import Credentials

try:
    import MetaTrader5 as mt5
except ImportError:  # 実行時に分かりやすいメッセージを出す
    mt5 = None  # type: ignore[assignment]


class MT5Error(RuntimeError):
    """MT5 の初期化・ログインに失敗した場合に送出する例外。"""


# terminal64.exe を探す代表的なインストール先候補。
_TERMINAL_PATH_CANDIDATES: tuple[str, ...] = (
    r"C:\Program Files\OANDA MetaTrader 5\terminal64.exe",
    r"C:\Program Files\OANDA-MetaTrader 5\terminal64.exe",
    r"C:\Program Files\OANDA Securities MetaTrader 5\terminal64.exe",
    r"C:\Program Files\MetaTrader 5\terminal64.exe",
    r"C:\Program Files (x86)\OANDA MetaTrader 5\terminal64.exe",
)

# ワイルドカード検索でも探す（社名違い・バージョン差異に対応）。
_TERMINAL_GLOB_PATTERNS: tuple[str, ...] = (
    r"C:\MT5\*\terminal64.exe",
    r"C:\Program Files\*MetaTrader 5*\terminal64.exe",
    r"C:\Program Files\*OANDA*\terminal64.exe",
    os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal\*\terminal64.exe"),
)


def _ensure_package() -> None:
    if mt5 is None:
        raise MT5Error(
            "MetaTrader5 パッケージが見つかりません。\n"
            "  pip install MetaTrader5\n"
            "を実行してください（Windows 専用）。"
        )


def detect_terminal_path() -> str | None:
    """terminal64.exe のパスを自動検出する。見つからなければ None。"""
    for cand in _TERMINAL_PATH_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    for pattern in _TERMINAL_GLOB_PATTERNS:
        matches = sorted(glob(pattern))
        if matches:
            return matches[0]
    return None


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
        timeout_ms: int = 120_000,
        init_retries: int = 3,
    ) -> None:
        self.credentials = credentials
        # 端末パスの優先順位:
        #   引数 > 選択した口座プロファイルのパス > 環境変数 > 自動検出
        self.terminal_path = (
            terminal_path
            or getattr(credentials, "terminal_path", None)
            or os.getenv("MT5_TERMINAL_PATH")
            or detect_terminal_path()
        )
        self.timeout_ms = timeout_ms
        self.init_retries = max(1, init_retries)
        self._connected = False

    def _initialize_ipc(self) -> None:
        """端末に接続して IPC 経路を確立する。

        ログイン情報は **渡さない**。これにより、既に起動・ログイン済みの
        端末へそのままアタッチでき、同一口座の二重ログインによる切断
        (disconnected) を避けられる。ログインが必要な場合は後段の
        ``mt5.login()`` で行う。
        """
        init_kwargs: dict[str, object] = {"timeout": self.timeout_ms}
        if self.terminal_path:
            init_kwargs["path"] = self.terminal_path

        last_code: tuple[int, str] | None = None
        for attempt in range(1, self.init_retries + 1):
            if mt5.initialize(**init_kwargs):
                return
            last_code = mt5.last_error()
            # 端末起動待ちの可能性があるため少し待って再試行
            if attempt < self.init_retries:
                time.sleep(3)

        code, msg = last_code or (0, "unknown")
        hint = self._ipc_hint() if code == -10005 else ""
        path_info = self.terminal_path or "(未検出)"
        raise MT5Error(
            f"MT5 の初期化に失敗しました (code={code}): {msg}\n"
            f"  使用した端末パス: {path_info}{hint}"
        )

    @staticmethod
    def _ipc_hint() -> str:
        return (
            "\n\n[IPC timeout の対処]\n"
            "  1. 接続したい『その』インスタンスを手動で起動する。\n"
            "     例: エクスプローラで C:\\MT5\\OANDA_FX\\terminal64.exe を実行。\n"
            "     ※ 別フォルダ/別アプリの MT5 を開いても接続先にはなりません。\n"
            "  2. その端末で対象口座にログインし、画面右下が緑(接続済み)であること。\n"
            "  3. メニュー > ツール > オプション > エキスパートアドバイザ で\n"
            "     『アルゴリズム取引を許可する』を有効化。\n"
            "  4. 同じ口座を別の MT5 でも開いていると二重ログインで切断されます。\n"
            "     接続先以外の MT5（Windows アプリ版など）は閉じてください。\n"
            "  5. Python(64bit) と端末(64bit) のビット数を一致させる。"
        )

    def _login_if_needed(self) -> None:
        """必要な場合のみログインする。

        既に目的の口座にログイン済みなら再ログインしない（二重ログインによる
        切断を避ける）。未ログイン/別口座の場合のみ ``mt5.login()`` を行う。
        """
        info = mt5.account_info()
        if info is not None and info.login == self.credentials.login:
            # 既に目的口座にログイン済み。アタッチのみで完了。
            return

        if not mt5.login(
            self.credentials.login,
            password=self.credentials.password,
            server=self.credentials.server,
        ):
            code, msg = mt5.last_error()
            mt5.shutdown()
            raise MT5Error(
                f"ログインに失敗しました (login={self.credentials.login}, "
                f"server={self.credentials.server!r}, code={code}): {msg}\n"
                "  ログイン番号・パスワード・サーバー名が正しいか確認してください。\n"
                "  ※ サーバー名は端末のログイン画面の表記に一致させる必要があります"
                " (例: 'OANDA-Japan MT5 Live')。"
            )

    def connect(self) -> "MT5Connection":
        _ensure_package()

        self._initialize_ipc()
        self._login_if_needed()

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
