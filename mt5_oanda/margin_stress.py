"""価格下落ストレステスト：証拠金維持率の安全度チェック。

dip buying(押し目買い)で現値より下に buy limit を多数配備している前提で、
『ドル円が N 円下落したら証拠金維持率が安全圏に残るか』を評価する。

通常の含み損評価と異なり、下落の過程で **発動する待機注文(buy limit 等)を
約定済み建玉として加算**する点が重要。これにより、下落で建玉とロットが
増え、必要証拠金も含み損も増える効果を反映する。

金額計算は MT5 の ``order_calc_profit`` / ``order_calc_margin`` を用い、
通貨換算・コントラクトサイズ・レバレッジを正確に反映する(取得不能時は
JPY 建て前提の近似でフォールバック)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .market_data import ensure_symbol

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]


# 注文/ポジション種別
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5

# 下落(価格が下がる)局面で発動する待機注文の種別
_TRIGGER_ON_DROP = (ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_STOP)
_BUY_SIDE_ORDERS = (ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_BUY_STOP)


def _require() -> None:
    if mt5 is None:
        raise RuntimeError("MetaTrader5 パッケージが利用できません。")


@dataclass
class Scenario:
    """ある下落幅における口座状態。"""

    drop: float
    triggered_orders: int
    triggered_volume: float
    equity: float
    used_margin: float
    free_margin: float
    margin_level: float  # 証拠金維持率[%]、使用証拠金0なら inf
    status: str          # "OK" / "マージンコール" / "ロスカット"


@dataclass
class StressReport:
    account: dict[str, object]
    symbols: list[str]
    current_prices: dict[str, float]
    n_positions: int
    n_orders: int
    stop_out_level: float
    margin_call_level: float
    headline: Scenario
    ladder: list[Scenario] = field(default_factory=list)
    critical_margin_call: float | None = None
    critical_stop_out: float | None = None


def _ref_price(symbol: str) -> float:
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None and tick.bid:
        return float(tick.bid)
    si = mt5.symbol_info(symbol)
    if si is not None and si.bid:
        return float(si.bid)
    return 0.0


def _contract_size(symbol: str) -> float:
    si = mt5.symbol_info(symbol)
    return float(si.trade_contract_size) if si is not None else 100_000.0


def _calc_profit(action: int, symbol: str, volume: float, p_open: float, p_close: float) -> float:
    val = mt5.order_calc_profit(action, symbol, volume, p_open, p_close)
    if val is not None:
        return float(val)
    # フォールバック: JPY 建て・JPY 決済通貨を仮定した近似
    sign = 1.0 if action == ORDER_TYPE_BUY else -1.0
    return (p_close - p_open) * volume * _contract_size(symbol) * sign


def _calc_margin(action: int, symbol: str, volume: float, price: float, leverage: float) -> float:
    val = mt5.order_calc_margin(action, symbol, volume, price)
    if val is not None:
        return float(val)
    lev = leverage if leverage and leverage > 0 else 25.0
    return volume * _contract_size(symbol) * price / lev


def _status(margin_level: float, stop_out: float, margin_call: float) -> str:
    if margin_level == float("inf"):
        return "OK"
    if stop_out > 0 and margin_level <= stop_out:
        return "ロスカット"
    if margin_call > 0 and margin_level <= margin_call:
        return "マージンコール"
    return "OK"


def run_stress(
    *,
    symbol_filter: str | None = None,
    headline_drop: float = 3.0,
    max_drop: float = 10.0,
    step: float = 1.0,
    fine_step: float = 0.05,
    stop_out_level: float | None = None,
    margin_call_level: float | None = None,
) -> StressReport:
    """ストレステストを実行して結果を返す。

    Args:
        symbol_filter: 対象銘柄を限定(例: "USDJPY")。None なら保有/注文の全銘柄。
        headline_drop: 主判定に用いる下落幅(価格単位、JPYペアなら「円」)。
        max_drop/step: シナリオ表の範囲と刻み。
        fine_step:     臨界下落幅を探す際の細かい刻み。
        stop_out_level/margin_call_level: ロスカット/マージンコール水準[%]。
            None ならサーバー(口座情報)の値を使用。
    """
    _require()

    acc_info = mt5.account_info()
    if acc_info is None:
        code, msg = mt5.last_error()
        raise RuntimeError(f"口座情報を取得できません (code={code}): {msg}")
    acc = acc_info._asdict()

    balance = float(acc.get("balance", 0.0))
    leverage = float(acc.get("leverage", 0.0))
    so_so = float(stop_out_level if stop_out_level is not None else acc.get("margin_so_so", 0.0))
    so_call = float(
        margin_call_level if margin_call_level is not None else acc.get("margin_so_call", 0.0)
    )

    positions = list(mt5.positions_get() or [])
    orders = list(mt5.orders_get() or [])
    if symbol_filter:
        positions = [p for p in positions if p.symbol == symbol_filter]
        orders = [o for o in orders if o.symbol == symbol_filter]

    symbols = sorted({p.symbol for p in positions} | {o.symbol for o in orders})
    for s in symbols:
        ensure_symbol(s)
    current = {s: _ref_price(s) for s in symbols}

    def state_at(drop: float) -> Scenario:
        new_price = {s: current[s] - drop for s in symbols}
        equity = balance
        used = 0.0
        trig = 0
        trig_vol = 0.0

        # 既存ポジション
        for p in positions:
            action = ORDER_TYPE_BUY if p.type == 0 else ORDER_TYPE_SELL
            close = new_price[p.symbol]
            equity += _calc_profit(action, p.symbol, p.volume, p.price_open, close) + float(p.swap)
            used += _calc_margin(action, p.symbol, p.volume, close, leverage)

        # 下落で発動する待機注文(buy limit / sell stop)→ 約定建玉として加算
        for o in orders:
            if o.type not in _TRIGGER_ON_DROP:
                continue
            sym = o.symbol
            # 現値から new_price まで下げる過程で価格に到達すれば発動
            if not (new_price[sym] <= o.price_open <= current[sym] + 1e-9):
                continue
            trig += 1
            trig_vol += float(o.volume_current)
            action = ORDER_TYPE_BUY if o.type in _BUY_SIDE_ORDERS else ORDER_TYPE_SELL
            close = new_price[sym]
            equity += _calc_profit(action, sym, o.volume_current, o.price_open, close)
            used += _calc_margin(action, sym, o.volume_current, close, leverage)

        ml = (equity / used * 100.0) if used > 0 else float("inf")
        return Scenario(
            drop=drop,
            triggered_orders=trig,
            triggered_volume=round(trig_vol, 2),
            equity=equity,
            used_margin=used,
            free_margin=equity - used,
            margin_level=ml,
            status=_status(ml, so_so, so_call),
        )

    headline = state_at(headline_drop)

    # シナリオ表(0 〜 max_drop)
    ladder: list[Scenario] = []
    d = 0.0
    while d <= max_drop + 1e-9:
        ladder.append(state_at(round(d, 4)))
        d += step

    # 臨界下落幅(細かく走査)
    critical_call: float | None = None
    critical_so: float | None = None
    scan_max = max(max_drop, 50.0)
    d = 0.0
    while d <= scan_max + 1e-9:
        sc = state_at(round(d, 4))
        if critical_call is None and so_call > 0 and sc.margin_level <= so_call:
            critical_call = round(d, 2)
        if critical_so is None and so_so > 0 and sc.margin_level <= so_so:
            critical_so = round(d, 2)
            break
        d += fine_step

    return StressReport(
        account=acc,
        symbols=symbols,
        current_prices=current,
        n_positions=len(positions),
        n_orders=len(orders),
        stop_out_level=so_so,
        margin_call_level=so_call,
        headline=headline,
        ladder=ladder,
        critical_margin_call=critical_call,
        critical_stop_out=critical_so,
    )
