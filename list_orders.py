#!/usr/bin/env python3
"""OANDA 証券の口座にログインし、オープン中の注文を一覧表示するプログラム。

特徴:
    - ユーザーID(ログイン番号)・パスワード・サーバー名はソースに直書きせず、
      起動時に対話入力する（パスワードは画面非表示）。
    - 登録済みの複数口座から選択して切り替え可能。
    - 待機注文(orders)に加え、保有ポジション(positions)も表示。

使い方:
    python list_orders.py
    python list_orders.py --symbol USDJPY
    python list_orders.py --positions-only
"""

from __future__ import annotations

import argparse
import sys

from mt5_oanda import (
    MT5Connection,
    MT5Error,
    get_open_orders,
    get_open_positions,
    prompt_credentials,
)

try:
    from tabulate import tabulate
except ImportError:  # tabulate 未導入でも簡易表示で動作させる
    tabulate = None  # type: ignore[assignment]


def _render(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "  (該当なし)"
    headers = list(rows[0].keys())
    table = [[r[h] for h in headers] for r in rows]
    if tabulate is not None:
        return tabulate(table, headers=headers, tablefmt="github")
    # フォールバック: タブ区切り
    lines = ["\t".join(headers)]
    lines += ["\t".join(str(c) for c in row) for row in table]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OANDA(MT5) のオープン注文・ポジションを一覧表示します。"
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="銘柄でフィルタ（例: USDJPY）。未指定なら全銘柄。",
    )
    parser.add_argument(
        "--orders-only",
        action="store_true",
        help="待機注文(orders)のみ表示する。",
    )
    parser.add_argument(
        "--positions-only",
        action="store_true",
        help="保有ポジション(positions)のみ表示する。",
    )
    parser.add_argument(
        "--terminal-path",
        default=None,
        help=(
            "MetaTrader5 端末(terminal64.exe)のパス。"
            "自動検出に失敗する/IPC timeout になる場合に指定する。"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    show_orders = not args.positions_only
    show_positions = not args.orders_only

    print("=== OANDA (MetaTrader 5) オープン注文一覧 ===\n")

    try:
        credentials = prompt_credentials()
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。")
        return 130

    try:
        with MT5Connection(credentials, terminal_path=args.terminal_path) as conn:
            summary = conn.account_summary()
            print(
                f"\nログイン成功: login={summary.get('login')} "
                f"name={summary.get('name')!r} server={summary.get('server')} "
                f"balance={summary.get('balance')} {summary.get('currency')}\n"
            )

            if show_orders:
                orders = get_open_orders(symbol=args.symbol)
                print(f"--- 待機注文 (orders): {len(orders)} 件 ---")
                print(_render([o.as_dict() for o in orders]))
                print()

            if show_positions:
                positions = get_open_positions(symbol=args.symbol)
                print(f"--- 保有ポジション (positions): {len(positions)} 件 ---")
                print(_render([p.as_dict() for p in positions]))
                print()

    except MT5Error as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
