#!/usr/bin/env python3
"""価格下落ストレステスト：証拠金維持率の安全度チェック。

dip buying で現値より下に buy limit を多数配備している前提で、
『ドル円が N 円下落したら証拠金維持率が安全圏に残るか』を評価する。
下落で発動する buy limit を約定建玉として織り込むのが特徴。

認証は他スクリプトと同様、起動時に対話入力する(直書きしない)。

使い方:
    python check_margin_stress.py                 # 既定: USDJPY 全体, 3円下落を主判定
    python check_margin_stress.py --symbol USDJPY --drop 3 --max-drop 15 --step 1
    python check_margin_stress.py --stop-out-level 100 --margin-call-level 120
"""

from __future__ import annotations

import argparse
import sys

from mt5_oanda import MT5Connection, MT5Error, prompt_credentials
from mt5_oanda.display import render_table
from mt5_oanda.margin_stress import Scenario, run_stress


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="価格下落時の証拠金維持率ストレステスト(待機注文の発動を考慮)。"
    )
    p.add_argument("--symbol", default=None, help="対象銘柄を限定(例: USDJPY)。既定は全銘柄。")
    p.add_argument("--drop", type=float, default=3.0, help="主判定の下落幅(価格単位、既定 3.0)")
    p.add_argument("--max-drop", type=float, default=15.0, help="シナリオ表の最大下落幅(既定 15)")
    p.add_argument("--step", type=float, default=1.0, help="シナリオ表の刻み(既定 1.0)")
    p.add_argument(
        "--stop-out-level", type=float, default=None,
        help="ロスカット水準[%%]。未指定なら口座情報の値を使用。",
    )
    p.add_argument(
        "--margin-call-level", type=float, default=None,
        help="マージンコール水準[%%]。未指定なら口座情報の値を使用。",
    )
    p.add_argument("--terminal-path", default=None, help="terminal64.exe のパス")
    return p.parse_args(argv)


def _yen(x: float) -> str:
    if x == float("inf"):
        return "∞"
    return f"{x:,.0f}"


def _ml(x: float) -> str:
    return "∞" if x == float("inf") else f"{x:,.1f}"


def _print_current(rep) -> None:
    acc = rep.account
    print(
        f"口座: login={acc.get('login')} name={acc.get('name')!r} "
        f"server={acc.get('server')}"
    )
    print(
        f"通貨: {acc.get('currency')}  レバレッジ: {acc.get('leverage')}倍  "
        f"ロスカット水準: {rep.stop_out_level:g}%  "
        f"マージンコール水準: {rep.margin_call_level:g}%"
    )
    print(
        f"残高: {_yen(float(acc.get('balance', 0)))}  "
        f"有効証拠金: {_yen(float(acc.get('equity', 0)))}  "
        f"使用証拠金: {_yen(float(acc.get('margin', 0)))}  "
        f"余剰証拠金: {_yen(float(acc.get('margin_free', 0)))}  "
        f"証拠金維持率: {_ml(float(acc.get('margin_level', 0)) or float('inf'))}%"
    )
    syms = ", ".join(
        f"{s}={rep.current_prices[s]:g}" for s in rep.symbols
    ) or "(対象なし)"
    print(f"対象銘柄/現値: {syms}")
    print(f"保有ポジション: {rep.n_positions}件  待機注文(対象): {rep.n_orders}件")


def _print_headline(rep) -> None:
    h: Scenario = rep.headline
    mark = {"OK": "✅ 安全圏", "マージンコール": "⚠️ マージンコール", "ロスカット": "🛑 ロスカット"}
    print(f"\n=== ストレステスト: {h.drop:g} 下落した場合 ===")
    print(
        f"発動する待機注文: {h.triggered_orders}件 "
        f"(追加 {h.triggered_volume:g} lot)"
    )
    print(
        f"有効証拠金: {_yen(h.equity)}  使用証拠金: {_yen(h.used_margin)}  "
        f"余剰証拠金: {_yen(h.free_margin)}"
    )
    print(
        f"証拠金維持率: {_ml(h.margin_level)}%  → 判定: "
        f"{mark.get(h.status, h.status)}"
    )


def _print_ladder(rep) -> None:
    headers = ["下落幅", "発動注文", "追加lot", "有効証拠金", "使用証拠金", "余剰証拠金", "維持率%", "状態"]
    aligns = ["right", "right", "right", "right", "right", "right", "right", "center"]
    rows = []
    for sc in rep.ladder:
        rows.append([
            f"{sc.drop:g}",
            sc.triggered_orders,
            f"{sc.triggered_volume:g}",
            _yen(sc.equity),
            _yen(sc.used_margin),
            _yen(sc.free_margin),
            _ml(sc.margin_level),
            sc.status,
        ])
    print("\n--- 下落シナリオ別の証拠金維持率 ---")
    print(render_table(headers, rows, aligns))


def _print_critical(rep) -> None:
    print("\n--- 余裕度(現値からどれだけ下げると抵触するか) ---")
    if rep.critical_margin_call is not None:
        print(f"マージンコール到達: 約 {rep.critical_margin_call:g} の下落")
    else:
        print("マージンコール到達: シナリオ範囲では未到達")
    if rep.critical_stop_out is not None:
        sym = rep.symbols[0] if rep.symbols else ""
        approx = ""
        if sym:
            approx = f" (例: {sym} ≈ {rep.current_prices[sym] - rep.critical_stop_out:g})"
        print(f"ロスカット到達: 約 {rep.critical_stop_out:g} の下落{approx}")
    else:
        print("ロスカット到達: シナリオ範囲では未到達(十分な余裕)")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("=== 証拠金維持率 下落ストレステスト ===\n")

    try:
        credentials = prompt_credentials()
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。")
        return 130

    try:
        with MT5Connection(credentials, terminal_path=args.terminal_path):
            rep = run_stress(
                symbol_filter=args.symbol,
                headline_drop=args.drop,
                max_drop=args.max_drop,
                step=args.step,
                stop_out_level=args.stop_out_level,
                margin_call_level=args.margin_call_level,
            )

        print()
        _print_current(rep)

        if rep.n_positions == 0 and rep.n_orders == 0:
            print("\n保有ポジションも対象の待機注文もありません。")
            return 0

        _print_headline(rep)
        _print_ladder(rep)
        _print_critical(rep)

        print(
            "\n* 維持率 = 有効証拠金 / 使用証拠金 × 100。"
            "下落で発動する buy limit を約定建玉として加算済み。"
            "発注価格・スプレッド・スワップ・約定スリッページは簡略化しています。"
        )

    except MT5Error as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
