"""相場データ取得ユーティリティ。

MT5 の時刻まわりは扱いが厄介なため、本モジュールで吸収する:

    - MT5 が返すバー/ティックの ``time`` は **ブローカーのサーバー時刻** を
      Unix エポックとして表したもの（UTC からのズレを含む）。
    - 本ツールが扱いたいのは **日本時間(JST, UTC+9)** の 9:55 前後。

そこで、ライブティックからサーバーの UTC オフセットを推定し、取得した
各バーの時刻を JST へ変換して扱う。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]


JST = timezone(timedelta(hours=9))


def _require() -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 パッケージが利用できません。")


def ensure_symbol(symbol: str) -> None:
    """銘柄を気配値表示に追加して利用可能にする。"""
    _require()
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(
            f"銘柄 {symbol!r} が見つかりません。端末の気配値表示で銘柄名を確認してください。"
        )
    # 既に表示済みでも冪等。選択するとヒストリ取得の対象になる。
    mt5.symbol_select(symbol, True)
    # ティックを起こしてデータ購読を促す
    mt5.symbol_info_tick(symbol)


def get_server_utc_offset_hours(symbol: str) -> int:
    """ブローカーのサーバー時刻が UTC から何時間ずれているかを推定する。

    ライブティックのサーバー時刻と実 UTC を比較して、時間単位に丸めて返す。
    多くのブローカーは EET(UTC+2/+3) を採用している。
    """
    _require()
    ensure_symbol(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or not tick.time:
        return 0
    server_epoch = float(tick.time)
    utc_epoch = time.time()
    return int(round((server_epoch - utc_epoch) / 3600.0))


def pip_size(symbol: str) -> float:
    """1pip の価格幅を返す（JPY ペアなら 0.01 など）。"""
    _require()
    info = mt5.symbol_info(symbol)
    if info is None:
        return 0.01
    point = info.point
    # 3桁/5桁クォートでは 1pip = 10point
    return point * 10 if info.digits in (3, 5) else point


def _rates_to_jst_bars(
    rates, server_offset_hours: int
) -> dict[tuple, dict[str, float]]:
    offset = server_offset_hours * 3600
    bars: dict[tuple, dict[str, float]] = {}
    for r in rates:
        # サーバー時刻エポック -> 真の UTC エポック -> JST
        true_utc = int(r["time"]) - offset
        dt = datetime.fromtimestamp(true_utc, tz=JST)
        bars[(dt.date(), dt.hour, dt.minute)] = {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
        }
    return bars


def fetch_m1_bars_jst(
    symbol: str,
    jst_from: datetime,
    jst_to: datetime,
    server_offset_hours: int,
    *,
    retries: int = 8,
    wait_sec: float = 1.5,
) -> dict[tuple, dict[str, float]]:
    """指定 JST 期間の M1 バーを取得し、JST キーで辞書化する。

    取得戦略:
        1. 日付範囲指定(copy_rates_range) を最優先。ヒストリDBから指定期間を
           丸ごと取得でき、チャートのバー数上限(例: 5万)に縛られにくい。
        2. それが空なら、位置指定(copy_rates_from_pos)を本数大→小で試す。
        3. さらに直近時刻起点(copy_rates_from)でダウンロードを促す。
        ヒストリ未取得時は最初の数回 0 本が返るため、待機しつつリトライする。

    Returns:
        {(date, hour, minute): {"open","high","low","close"}, ...}
    """
    _require()
    ensure_symbol(symbol)

    now_utc = datetime.now(timezone.utc)
    # 入力解釈のズレ・DST を吸収するため前後 1 日広げる
    utc_from = jst_from.astimezone(timezone.utc) - timedelta(days=1)
    utc_to = jst_to.astimezone(timezone.utc) + timedelta(days=1)

    total_minutes = int((jst_to - jst_from).total_seconds() // 60) + 2 * 1440
    ladder = [200_000, 100_000, 50_000, 20_000, 10_000, 5_000, 2_000, 1_000]
    pos_counts = sorted({total_minutes, *[c for c in ladder if c < total_minutes]}, reverse=True)

    best: dict[tuple, dict[str, float]] = {}
    for _ in range(max(1, retries)):
        # 1) 範囲指定(最優先)
        ranged = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)
        if ranged is not None and len(ranged) > 0:
            bars = _rates_to_jst_bars(ranged, server_offset_hours)
            if len(bars) > len(best):
                best = bars

        # 2) 位置指定(本数大→小)。範囲指定より多く取れた場合のみ採用
        for c in pos_counts:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, c)
            if rates is not None and len(rates) > 0:
                bars = _rates_to_jst_bars(rates, server_offset_hours)
                if len(bars) > len(best):
                    best = bars
                break

        if best:
            return best

        # 3) ダウンロードのトリガ
        mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, now_utc, 5_000)
        time.sleep(wait_sec)

    return best


def bars_jst_span(bars: dict[tuple, dict[str, float]]) -> tuple[str, str]:
    """取得済みバーが覆う JST の最小・最大の日付時刻(診断用)を返す。"""
    if not bars:
        return ("", "")
    keys = sorted(bars.keys())
    a, b = keys[0], keys[-1]
    return (
        f"{a[0].isoformat()} {a[1]:02d}:{a[2]:02d}",
        f"{b[0].isoformat()} {b[1]:02d}:{b[2]:02d}",
    )


def price_at(
    bars: dict[tuple, dict[str, float]],
    jst_dt: datetime,
    field: str = "open",
    search_back_min: int = 5,
) -> float | None:
    """指定 JST 時刻の価格を返す。

    ちょうどの分のバーが無い場合は、最大 ``search_back_min`` 分だけ
    さかのぼって直近のバーを採用する。
    """
    for i in range(search_back_min + 1):
        t = jst_dt - timedelta(minutes=i)
        key = (t.date(), t.hour, t.minute)
        bar = bars.get(key)
        if bar is not None:
            return bar[field]
    return None
