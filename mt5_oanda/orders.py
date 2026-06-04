"""オープン中の注文(pending orders)・ポジション(open positions)を取得する。

MetaTrader 5 の用語:
    - order    : まだ約定していない待機注文(指値・逆指値など)。
    - position : 既に約定して保有中の建玉。

一般に「オープンされている注文」は待機注文を指しますが、保有中の建玉も
合わせて確認したいことが多いため、本モジュールでは両方を取得できます。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]


# 注文タイプ番号 -> 人間可読ラベル
_ORDER_TYPE_LABELS = {
    0: "BUY",
    1: "SELL",
    2: "BUY_LIMIT",
    3: "SELL_LIMIT",
    4: "BUY_STOP",
    5: "SELL_STOP",
    6: "BUY_STOP_LIMIT",
    7: "SELL_STOP_LIMIT",
    8: "CLOSE_BY",
}

_POSITION_TYPE_LABELS = {0: "BUY", 1: "SELL"}


def _fmt_time(epoch_seconds: int | float | None) -> str:
    if not epoch_seconds:
        return ""
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


@dataclass
class OrderRecord:
    """待機注文 1 件分の表示用レコード。"""

    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    time_setup: str
    comment: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class PositionRecord:
    """保有ポジション 1 件分の表示用レコード。"""

    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    profit: float
    swap: float
    time: str
    comment: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def get_open_orders(symbol: str | None = None) -> list[OrderRecord]:
    """オープン中の待機注文を取得する。

    Args:
        symbol: 銘柄でフィルタする場合に指定（例: "USDJPY"）。None なら全件。
    """
    if mt5 is None:
        raise RuntimeError("MetaTrader5 パッケージが利用できません。")

    raw = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
    if raw is None:
        return []

    records: list[OrderRecord] = []
    for o in raw:
        records.append(
            OrderRecord(
                ticket=o.ticket,
                symbol=o.symbol,
                type=_ORDER_TYPE_LABELS.get(o.type, f"TYPE_{o.type}"),
                volume=o.volume_current,
                price_open=o.price_open,
                sl=o.sl,
                tp=o.tp,
                price_current=o.price_current,
                time_setup=_fmt_time(o.time_setup),
                comment=o.comment,
            )
        )
    return records


def get_open_positions(symbol: str | None = None) -> list[PositionRecord]:
    """保有中のポジションを取得する。

    Args:
        symbol: 銘柄でフィルタする場合に指定。None なら全件。
    """
    if mt5 is None:
        raise RuntimeError("MetaTrader5 パッケージが利用できません。")

    raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if raw is None:
        return []

    records: list[PositionRecord] = []
    for p in raw:
        records.append(
            PositionRecord(
                ticket=p.ticket,
                symbol=p.symbol,
                type=_POSITION_TYPE_LABELS.get(p.type, f"TYPE_{p.type}"),
                volume=p.volume,
                price_open=p.price_open,
                sl=p.sl,
                tp=p.tp,
                price_current=p.price_current,
                profit=p.profit,
                swap=p.swap,
                time=_fmt_time(p.time),
                comment=p.comment,
            )
        )
    return records
