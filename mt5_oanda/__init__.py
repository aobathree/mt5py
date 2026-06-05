"""mt5_oanda: OANDA 証券の複数口座へ MetaTrader 5 経由でアクセスするためのユーティリティ。

公開 API:
    - Credentials / prompt_credentials : 起動時に認証情報を対話取得する
    - MT5Connection                    : 接続/ログイン/切断を管理する context manager
    - get_open_orders / get_open_positions : 注文・ポジション取得
"""

from .accounts import OANDA_SERVERS, KNOWN_ACCOUNTS, AccountProfile
from .credentials import Credentials, prompt_credentials
from .connection import MT5Connection, MT5Error
from .orders import (
    OrderRecord,
    PositionRecord,
    get_open_orders,
    get_open_positions,
)
from .tokyo_fix import FixingDay, collect_fixing_days, detailed_stats, summarize

__all__ = [
    "OANDA_SERVERS",
    "KNOWN_ACCOUNTS",
    "AccountProfile",
    "Credentials",
    "prompt_credentials",
    "MT5Connection",
    "MT5Error",
    "OrderRecord",
    "PositionRecord",
    "get_open_orders",
    "get_open_positions",
    "FixingDay",
    "collect_fixing_days",
    "detailed_stats",
    "summarize",
]

__version__ = "0.1.0"
