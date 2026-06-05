#!/usr/bin/env python3
"""東京仲値(9:55 JST 前後)のドル円値動きを検証・記録するツール。

過去のヒストリカル M1 データを取得し、

    - run_up   : 仲値前(既定 09:00) -> 仲値(09:55) の変化[pips]
    - reversal : 仲値(09:55) -> 仲値後(既定 10:30) の変化[pips]

を日次で計測し、全体 / 五十日(ごとおび) / それ以外 に分けて統計を表示する。
``--csv`` を付けると日次の明細を CSV へ保存できる(記録用)。

認証は他のスクリプトと同様、起動時に対話入力する(直書きしない)。

使い方:
    python analyze_tokyo_fix.py
    python analyze_tokyo_fix.py --symbol USDJPY --days 120 --csv nakane.csv
    python analyze_tokyo_fix.py --pre 09:00 --fix 09:55 --post 10:30
"""

from __future__ import annotations

import argparse
import csv
import sys

from mt5_oanda import MT5Connection, MT5Error, prompt_credentials
from mt5_oanda.display import render_table
from mt5_oanda.tokyo_fix import collect_fixing_days, detailed_stats, summarize


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="東京仲値(9:55 JST)前後のドル円値動きを検証・記録する。"
    )
    p.add_argument("--symbol", default="USDJPY", help="対象銘柄(既定: USDJPY)")
    p.add_argument("--days", type=int, default=90, help="遡る暦日数(既定: 90)")
    p.add_argument("--pre", default="09:00", help="仲値前の基準時刻 HH:MM(既定 09:00)")
    p.add_argument("--fix", default="09:55", help="仲値時刻 HH:MM(既定 09:55)")
    p.add_argument("--post", default="10:30", help="仲値後の基準時刻 HH:MM(既定 10:30)")
    p.add_argument(
        "--tz-offset-hours",
        type=int,
        default=None,
        help="ブローカーのサーバーUTCオフセット(時間)。未指定なら自動推定。",
    )
    p.add_argument("--csv", default=None, help="日次明細を保存する CSV パス")
    p.add_argument(
        "--terminal-path",
        default=None,
        help="MetaTrader5 端末(terminal64.exe)のパス。",
    )
    p.add_argument(
        "--show-rows",
        type=int,
        default=10,
        help="コンソールに表示する直近明細の行数(既定 10、0 で非表示)",
    )
    return p.parse_args(argv)


def _fmt_stat(s: dict[str, object]) -> list[object]:
    return [s["n"], s["mean"], s["median"], s["stdev"], s["win_rate"]]


def _print_summary(meta: dict[str, object], summary: dict[str, dict]) -> None:
    print(
        f"\n対象: {meta['symbol']}  指定期間: {meta['from']} 〜 {meta['to']}  "
        f"集計営業日数: {meta['n_days']}  pip={meta['pip_size']}  "
        f"サーバーUTCオフセット: +{meta['server_offset_hours']}h"
    )
    print(
        f"計測点(JST): pre={meta['pre']}  fix={meta['fix']}  post={meta['post']}"
    )
    print(
        f"取得M1: {meta['n_raw_bars']} 本  "
        f"実データ範囲(JST): {meta['bars_jst_from'] or '(なし)'}"
        f" 〜 {meta['bars_jst_to'] or '(なし)'}"
    )
    if meta["n_days"] < 20:
        print(
            "※ 集計営業日数が少ないため統計は参考程度です。端末で USDJPY の "
            "M1 チャートを過去方向へ十分スクロールしてヒストリを増やすと、"
            "より長期間を集計できます。"
        )
    print()

    headers = ["指標", "区分", "n", "平均pips", "中央値", "標準偏差", "上昇率%"]
    aligns = ["left", "left", "right", "right", "right", "right", "right"]
    rows = []
    labels = {"all": "全体", "gotobi": "五十日", "non_gotobi": "非五十日"}
    for metric, jp in (("run_up", "仲値前→仲値"), ("reversal", "仲値→仲値後")):
        for subset in ("all", "gotobi", "non_gotobi"):
            rows.append([jp, labels[subset], *_fmt_stat(summary[subset][metric])])

    print(render_table(headers, rows, aligns))

    print(
        "\n* 上昇率% = 変化が +(プラス)だった日の割合。"
        "run_up が高いほど『仲値に向け上昇』、reversal が低いほど『仲値後に反落』の傾向。"
    )


def _fmt_p(p: object) -> str:
    if p is None or (isinstance(p, float) and p != p):  # None or NaN
        return "-"
    return f"{float(p):.3f}"


def _fmt_num(x: object, nd: int = 2) -> str:
    if x is None:
        return "-"
    return f"{float(x):.{nd}f}"


def _print_significance(detailed: dict) -> None:
    print("\n=== 有意性検定 (帰無仮説: 平均=0) ===")
    headers = [
        "指標", "区分", "n", "平均", "95%信頼区間", "p(t検定)", "符号検定p", "トリム平均", "判定",
    ]
    aligns = ["left", "left", "right", "right", "center", "right", "right", "right", "center"]
    rows = []
    labels = {"all": "全体", "gotobi": "五十日", "non_gotobi": "非五十日"}
    for metric, jp in (("run_up", "仲値前→仲値"), ("reversal", "仲値→仲値後")):
        for subset in ("all", "gotobi", "non_gotobi"):
            s = detailed[subset][metric]
            if s["ci_low"] is None:
                ci = "-"
            else:
                ci = f"[{_fmt_num(s['ci_low'],1)}, {_fmt_num(s['ci_high'],1)}]"
            ps = [p for p in (s["p_t"], s["sign_p"]) if isinstance(p, float) and p == p]
            verdict = "有意(5%)" if ps and min(ps) < 0.05 else "n.s."
            rows.append([
                jp, labels[subset], s["n"], _fmt_num(s["mean"]), ci,
                _fmt_p(s["p_t"]), _fmt_p(s["sign_p"]), _fmt_num(s["trimmed"]), verdict,
            ])
    print(render_table(headers, rows, aligns))
    print(
        "\n* p<0.05 で『平均が0と有意に異なる』。"
        "n.s.=有意差なし。トリム平均=上下10%除外で外れ値の影響を抑えた平均。"
    )


def _print_recent(records, n: int) -> None:
    if n <= 0 or not records:
        return
    recent = records[-n:]
    headers = ["date", "曜日", "五十日", "pre", "fix", "post", "run_up", "reversal"]
    aligns = ["left", "center", "center", "right", "right", "right", "right", "right"]
    rows = [
        [
            r.date,
            r.weekday,
            "○" if r.is_gotobi else "",
            r.price_pre,
            r.price_fix,
            r.price_post,
            r.run_up_pips,
            r.reversal_pips,
        ]
        for r in recent
    ]
    print(f"\n--- 直近 {len(recent)} 営業日の明細 ---")
    print(render_table(headers, rows, aligns))


def _write_csv(path: str, records) -> None:
    if not records:
        print("CSV: 保存対象データがありません。")
        return
    fieldnames = list(records[0].as_dict().keys())
    # Excel での文字化け回避のため utf-8-sig
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r.as_dict())
    print(f"\nCSV を保存しました: {path}  ({len(records)} 行)")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("=== 東京仲値(9:55 JST) ドル円値動き 検証ツール ===\n")

    try:
        credentials = prompt_credentials()
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。")
        return 130

    try:
        with MT5Connection(credentials, terminal_path=args.terminal_path):
            records, meta = collect_fixing_days(
                symbol=args.symbol,
                days=args.days,
                pre=args.pre,
                fix=args.fix,
                post=args.post,
                server_offset_hours=args.tz_offset_hours,
            )

        if not records:
            print("有効な日次データを集計できませんでした。診断情報:")
            print(f"  銘柄: {meta['symbol']}")
            print(f"  取得 M1 バー数: {meta['n_raw_bars']}")
            print(
                f"  バーのJST範囲: {meta['bars_jst_from'] or '(なし)'}"
                f" 〜 {meta['bars_jst_to'] or '(なし)'}"
            )
            print(f"  サーバーUTCオフセット(推定): +{meta['server_offset_hours']}h")
            print(
                f"  最新日の {meta['fix']} 周辺に存在する分足(時:分): "
                f"{meta['fix_minute_sample'] or '(なし)'}"
            )
            if meta["n_raw_bars"] == 0:
                print(
                    "\n→ M1 データが 0 本です。接続先インスタンス"
                    "(C:\\MT5\\OANDA_FX)で USDJPY を表示してヒストリを取得してください:\n"
                    "   1. 気配値表示で USDJPY を右クリック → チャート表示。\n"
                    "   2. 時間足を M1 にし、Home キー等で過去方向へスクロール"
                    "(数日〜数週間分ダウンロードされるまで)。\n"
                    "   3. 取得後にスクリプトを再実行。まずは短期間で試すのも有効:\n"
                    "      python analyze_tokyo_fix.py --days 10"
                )
            else:
                print(
                    "\n→ バーは取得できていますが、仲値時刻のバーが見つかりません。"
                    "サーバー時刻オフセットがずれている可能性があります。"
                    "上の『分足サンプル』が 09:55 を含むか確認し、ズレていれば "
                    "--tz-offset-hours で正しい値を指定してください。"
                )
            return 1

        summary = summarize(records)
        _print_summary(meta, summary)
        _print_significance(detailed_stats(records))
        _print_recent(records, args.show_rows)

        if args.csv:
            _write_csv(args.csv, records)

    except MT5Error as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
