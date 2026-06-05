"""軽量な統計検定(外部依存なし)。

平均が 0 と有意に異なるかを評価するための t 検定・符号検定・信頼区間・
トリム平均を、標準ライブラリ(math, statistics)のみで実装する。
Student-t の両側 p 値は、正則化不完全ベータ関数 I_x(a,b) を用いて算出する。
"""

from __future__ import annotations

import math
from statistics import fmean, median, stdev


def _betacf(a: float, b: float, x: float) -> float:
    MAXIT = 300
    EPS = 3.0e-16
    FPMIN = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """正則化不完全ベータ関数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(ln_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    """自由度 df の Student-t における P(|T| > |t|)。"""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return betai(df / 2.0, 0.5, x)


def t_critical(df: float, alpha: float = 0.05) -> float:
    """両側 alpha に対応する t 臨界値を二分法で求める。"""
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_two_sided_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def sign_test_p(values: list[float]) -> float:
    """符号検定(両側, 帰無仮説 中央値=0)。0 は除外。"""
    nz = [v for v in values if v != 0]
    n = len(nz)
    if n == 0:
        return float("nan")
    k = sum(1 for v in nz if v > 0)

    def cdf_le(j: int) -> float:
        return sum(math.comb(n, i) for i in range(0, j + 1)) / (2.0**n)

    p_le = cdf_le(k)
    p_ge = cdf_le(n - k)  # P(X>=k) = P(X<=n-k)
    return min(1.0, 2.0 * min(p_le, p_ge))


def trimmed_mean(values: list[float], prop: float = 0.1) -> float:
    """両側 prop 割を除外したトリム平均(外れ値の影響を抑える)。"""
    v = sorted(values)
    n = len(v)
    if n == 0:
        return float("nan")
    k = int(n * prop)
    core = v[k : n - k] if n - 2 * k > 0 else v
    return fmean(core)


def describe(values, *, trim_prop: float = 0.1, alpha: float = 0.05) -> dict[str, object]:
    """平均まわりの記述統計＋有意性指標をまとめて返す。"""
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return {
            "n": 0, "mean": None, "median": None, "stdev": None,
            "se": None, "t": None, "p_t": None, "ci_low": None,
            "ci_high": None, "win_rate": None, "sign_p": None, "trimmed": None,
        }

    mean = fmean(vals)
    med = median(vals)
    pos = sum(1 for v in vals if v > 0)
    win = 100.0 * pos / n

    if n >= 2:
        sd = stdev(vals)
        se = sd / math.sqrt(n)
        if se > 0:
            t = mean / se
            df = n - 1
            p_t = t_two_sided_p(t, df)
            tc = t_critical(df, alpha)
            ci_low, ci_high = mean - tc * se, mean + tc * se
        else:
            t, p_t, ci_low, ci_high = 0.0, 1.0, mean, mean
    else:
        sd = se = t = p_t = None
        ci_low = ci_high = None

    return {
        "n": n,
        "mean": mean,
        "median": med,
        "stdev": sd,
        "se": se,
        "t": t,
        "p_t": p_t,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "win_rate": win,
        "sign_p": sign_test_p(vals),
        "trimmed": trimmed_mean(vals, trim_prop),
    }
