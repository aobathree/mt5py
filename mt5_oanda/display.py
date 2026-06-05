"""全角(東アジア文字)幅を考慮したコンソール表整形。

``tabulate`` は全角文字の表示幅を 1 として扱うため、日本語を含む表で桁が
崩れる。本モジュールは ``unicodedata.east_asian_width`` を用いて表示幅を
正しく計算し、列を揃える(追加依存なし)。
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

_COL_SEP = "  "


def display_width(text: object) -> int:
    """文字列のコンソール表示幅を返す(全角=2, 半角=1)。"""
    s = "" if text is None else str(text)
    width = 0
    for ch in s:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _pad(text: object, width: int, align: str) -> str:
    s = "" if text is None else str(text)
    space = width - display_width(s)
    if space <= 0:
        return s
    if align == "right":
        return " " * space + s
    if align == "center":
        left = space // 2
        return " " * left + s + " " * (space - left)
    return s + " " * space


def render_table(
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
    aligns: Sequence[str] | None = None,
) -> str:
    """全角幅を考慮した表を文字列で返す。

    Args:
        headers: ヘッダ列。
        rows:    各行のセル列。
        aligns:  各列の寄せ ("left"/"right"/"center")。省略時は left。
    """
    cols = len(headers)
    str_rows = [["" if c is None else str(c) for c in row] for row in rows]

    widths = [display_width(h) for h in headers]
    for row in str_rows:
        for i in range(cols):
            if i < len(row):
                widths[i] = max(widths[i], display_width(row[i]))

    if aligns is None:
        aligns = ["left"] * cols

    lines = [
        _COL_SEP.join(_pad(headers[i], widths[i], "left") for i in range(cols)),
        _COL_SEP.join("-" * widths[i] for i in range(cols)),
    ]
    for row in str_rows:
        cells = []
        for i in range(cols):
            cell = row[i] if i < len(row) else ""
            cells.append(_pad(cell, widths[i], aligns[i]))
        lines.append(_COL_SEP.join(cells))
    return "\n".join(lines)
