"""東京仲値(9:55 JST 前後)のドル円値動きを検証・記録するロジック。

検証する代表的な経験則:
    - 仲値(9:55)に向けてドル円が上昇しやすい（実需のドル買い）。
    - 仲値決定後に反落しやすい。
    - 上記の傾向は『五十日(ごとおび)』に強く出やすい。

価格は各対象時刻の M1 バーの始値(open)を「その時刻の価格」として用いる。
"""

from __future__ import annotations

import calendar
import statistics
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta

from .market_data import (
    JST,
    bars_jst_span,
    fetch_m1_bars_jst,
    get_server_utc_offset_hours,
    pip_size,
    price_at,
)

_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass
class FixingDay:
    """1 営業日分の仲値ウィンドウ計測結果。"""

    date: str          # JST の日付 (YYYY-MM-DD)
    weekday: str       # 曜日(日本語)
    is_gotobi: bool    # 五十日か
    price_pre: float | None
    price_fix: float | None
    price_post: float | None
    run_up_pips: float | None      # 仲値に向けた変化(fix - pre)
    reversal_pips: float | None    # 仲値後の変化(post - fix)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def effective_gotobi_dates(target_dates: list[date]) -> set[date]:
    """五十日(5,10,15,20,25,末日)の『実際の決済営業日』集合を返す。

    名目日が土日の場合は直前の平日へ繰り上げる(一般的な慣行)。
    祝日は考慮しない(簡略化。必要なら祝日カレンダーで拡張)。
    """
    months = {(d.year, d.month) for d in target_dates}
    result: set[date] = set()
    for year, month in months:
        last_day = calendar.monthrange(year, month)[1]
        nominal_days = [5, 10, 15, 20, 25, last_day]
        for nd in nominal_days:
            d = date(year, month, min(nd, last_day))
            # 土(5)・日(6) なら直前の平日へ
            while d.weekday() >= 5:
                d -= timedelta(days=1)
            result.add(d)
    return result


def _hm(s: str) -> tuple[int, int]:
    """'HH:MM' -> (hour, minute)。"""
    h, m = s.split(":")
    return int(h), int(m)


def collect_fixing_days(
    symbol: str = "USDJPY",
    *,
    days: int = 90,
    pre: str = "09:00",
    fix: str = "09:55",
    post: str = "10:30",
    server_offset_hours: int | None = None,
) -> tuple[list[FixingDay], dict[str, object]]:
    """過去 ``days`` 日分の仲値ウィンドウを集計する。

    Returns:
        (per_day records, meta) のタプル。
        meta には symbol/pip/offset/期間などの情報を含む。
    """
    if server_offset_hours is None:
        server_offset_hours = get_server_utc_offset_hours(symbol)

    pip = pip_size(symbol)

    now_jst = datetime.now(JST)
    jst_to = now_jst
    jst_from = now_jst - timedelta(days=days)

    bars = fetch_m1_bars_jst(symbol, jst_from, jst_to, server_offset_hours)

    pre_h, pre_m = _hm(pre)
    fix_h, fix_m = _hm(fix)
    post_h, post_m = _hm(post)

    # 期間内(jst_from 以降)かつ取得済みバーに存在する JST 日付
    from_date = jst_from.date()
    all_dates = sorted({key[0] for key in bars if key[0] >= from_date})
    gotobi = effective_gotobi_dates(all_dates) if all_dates else set()

    # 診断用: 最新日付に存在する 09 時台のバー(時:分)サンプル
    fix_sample: list[str] = []
    if all_dates:
        latest = all_dates[-1]
        fix_sample = sorted(
            f"{h:02d}:{m:02d}"
            for (d, h, m) in bars
            if d == latest and h in (fix_h - 1, fix_h, fix_h + 1)
        )

    records: list[FixingDay] = []
    for d in all_dates:
        base = datetime(d.year, d.month, d.day, tzinfo=JST)
        p_pre = price_at(bars, base.replace(hour=pre_h, minute=pre_m))
        p_fix = price_at(bars, base.replace(hour=fix_h, minute=fix_m))
        p_post = price_at(bars, base.replace(hour=post_h, minute=post_m))

        # 仲値の価格が取れない日は非営業日とみなしてスキップ
        if p_fix is None:
            continue

        run_up = (p_fix - p_pre) / pip if p_pre is not None else None
        reversal = (p_post - p_fix) / pip if p_post is not None else None

        records.append(
            FixingDay(
                date=d.isoformat(),
                weekday=_WEEKDAY_JA[d.weekday()],
                is_gotobi=d in gotobi,
                price_pre=p_pre,
                price_fix=p_fix,
                price_post=p_post,
                run_up_pips=round(run_up, 1) if run_up is not None else None,
                reversal_pips=round(reversal, 1) if reversal is not None else None,
            )
        )

    span_from, span_to = bars_jst_span(bars)
    meta = {
        "symbol": symbol,
        "pip_size": pip,
        "server_offset_hours": server_offset_hours,
        "pre": pre,
        "fix": fix,
        "post": post,
        "from": jst_from.date().isoformat(),
        "to": jst_to.date().isoformat(),
        "n_days": len(records),
        "n_raw_bars": len(bars),
        "bars_jst_from": span_from,
        "bars_jst_to": span_to,
        "fix_minute_sample": fix_sample,
    }
    return records, meta


def _summarize(values: list[float]) -> dict[str, object]:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "win_rate": None}
    pos = sum(1 for v in vals if v > 0)
    return {
        "n": len(vals),
        "mean": round(statistics.fmean(vals), 2),
        "median": round(statistics.median(vals), 2),
        "stdev": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
        "win_rate": round(100.0 * pos / len(vals), 1),  # 上昇(>0)の割合(%)
    }


def _subsets(records: list[FixingDay]) -> dict[str, list[FixingDay]]:
    return {
        "all": records,
        "gotobi": [r for r in records if r.is_gotobi],
        "non_gotobi": [r for r in records if not r.is_gotobi],
    }


def summarize(records: list[FixingDay]) -> dict[str, dict[str, object]]:
    """run_up / reversal を 全体・五十日・非五十日 に分けて統計する。"""
    result: dict[str, dict[str, object]] = {}
    for name, rows in _subsets(records).items():
        result[name] = {
            "run_up": _summarize([r.run_up_pips for r in rows]),
            "reversal": _summarize([r.reversal_pips for r in rows]),
        }
    return result


def detailed_stats(records: list[FixingDay]) -> dict[str, dict[str, dict]]:
    """有意性検定(t検定/符号検定/信頼区間/トリム平均)を含む詳細統計。"""
    from .stats import describe

    result: dict[str, dict[str, dict]] = {}
    for name, rows in _subsets(records).items():
        result[name] = {
            "run_up": describe([r.run_up_pips for r in rows]),
            "reversal": describe([r.reversal_pips for r in rows]),
        }
    return result
