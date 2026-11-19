"""s183 — общие функции проб: периоды, вселенная криптоперпов Binance USDT-M, дневные агрегаты из 15-мин свечей,
спот Binance, корейские рынки к воне, снимки CMC, входы журналов (только время входа для пересечений).

Только охват данных, распределения признаков, ранговые связи и обороты корзин. Доходы после даты сигнала, сделки
и плацебо НЕ считаются (правило «гипотезы — до проверки»): все признаки — по данным строго до момента среза."""
import glob
import io
import json
import os
import pickle
import re
import zipfile

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s183"
DAY = 86400
PER = {
    "2020–2022": dict(k=f"{D}/s117/k_2020.pkl", f=f"{D}/s117/fund_2020.pkl", t0="2020-10-01", t1="2022-10-01",
                      spot="/home/user/mc_2020/s23/spotcache", kc=f"{D}/s88/oos2020/kc", kmap=f"{D}/s88/oos2020/map.pkl"),
    "2022–2024": dict(k=f"{D}/s117/k_oos.pkl", f=f"{D}/s117/fund_oos.pkl", t0="2022-10-01", t1="2024-10-01",
                      spot="/home/user/mc_oos/s23/spotcache", kc=f"{D}/s88/oos/kc", kmap=f"{D}/s88/oos/map.pkl"),
    "2024–2026": dict(k=f"{D}/s2/k2y.pkl", f=f"{D}/s2/fund2y.pkl", t0="2024-10-01", t1="2026-10-19",
                      spot=f"{D}/s23/spot1h.pkl", kc=f"{D}/s15", kmap=None),
}
PERS = list(PER)
# стейблкоины, индексы, металлы, сырьё, акции (список s179 + стейблкоины бота) — не криптовселенная
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "XAUT", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP", "USD1", "RLUSD", "XUSD", "BFUSD", "USDE", "BUSD", "DAI", "USTC", "EUR",
             "GBP", "AUD", "USDBRL", "AMZN", "COIN", "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSTR", "NVDA", "PLTR",
             "TSLA", "FOOTBALL"}
MULT = re.compile(r"^(1000000|100000|10000|1000|100|1M)(?=[A-Z0-9])")


def ts(x):
    return int(pd.Timestamp(x, tz="UTC").timestamp())


def base(perp):
    """1000PEPE → PEPE, 1000000MOG → MOG, 1MBABYDOGE → BABYDOGE; суффикс USDT убирается."""
    p = perp[:-4] if perp.endswith("USDT") else perp
    return MULT.sub("", p)


def mult(perp):
    p = perp[:-4] if perp.endswith("USDT") else perp
    m = MULT.match(p)
    if not m:
        return 1.0
    return 1e6 if m.group(1) == "1M" else float(m.group(1))


def bad_set():
    kind = pd.read_pickle(f"{D}/s12/perp_kind.pkl")
    return set(kind.get("tradfi", set())) | NONCRYPTO


def mondays(per):
    """Срезы — понедельники 00:00 UTC внутри периода."""
    t0, t1 = ts(PER[per]["t0"]), ts(PER[per]["t1"])
    d0 = pd.Timestamp(PER[per]["t0"], tz="UTC")
    d0 = d0 + pd.Timedelta(days=(7 - d0.weekday()) % 7)
    out = []
    t = int(d0.timestamp())
    while t < t1:
        out.append(t)
        t += 7 * DAY
    return np.array(out, np.int64)


def months(per):
    return (ts(PER[per]["t1"]) - ts(PER[per]["t0"])) / (30.4 * DAY)


def daily_from_15m(a):
    """15-мин свечи {t, o, h, l, c, qv, tb, n} → сутки UTC (только свечи с оборотом): o, h, l, c, qv, tb, n, nb (свечей
    с оборотом), rv (сумма квадратов 15-мин лог-доходностей), rvp (то же для положительных), mx15 (наибольшая
    15-мин доходность). Возвращает DataFrame с индексом начала суток (сек)."""
    t = np.asarray(a["t"], np.int64)
    qv = np.asarray(a["qv"], np.float64)
    live = qv > 0
    if live.sum() < 96:
        return None
    t = t[live]
    c = np.asarray(a["c"], np.float64)[live]
    o = np.asarray(a["o"], np.float64)[live]
    h = np.asarray(a["h"], np.float64)[live]
    l_ = np.asarray(a["l"], np.float64)[live]
    qv = qv[live]
    tb = np.asarray(a["tb"], np.float64)[live] if "tb" in a else np.full(len(t), np.nan)
    n = np.asarray(a["n"], np.float64)[live] if "n" in a else np.full(len(t), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.r_[np.nan, np.diff(np.log(c))]
    lr[np.r_[True, np.diff(t) != 900]] = np.nan        # разрыв сетки — без доходности
    g = t // DAY
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], len(t)] - 1
    lr0 = np.nan_to_num(lr)
    out = pd.DataFrame({
        "o": o[st], "h": np.maximum.reduceat(h, st), "l": np.minimum.reduceat(l_, st), "c": c[en],
        "qv": np.add.reduceat(qv, st), "tb": np.add.reduceat(np.nan_to_num(tb), st),
        "n": np.add.reduceat(np.nan_to_num(n), st), "nb": np.diff(np.r_[st, len(t)]),
        "rv": np.add.reduceat(lr0 ** 2, st), "rvp": np.add.reduceat(np.where(lr0 > 0, lr0 ** 2, 0.0), st),
        "mx15": np.maximum.reduceat(np.where(np.isnan(lr), -np.inf, lr), st),
    }, index=pd.Index(g[st] * DAY, name="d"))
    out.loc[~np.isfinite(out.mx15), "mx15"] = np.nan
    return out


def fund_daily(arr):
    """Фандинг [время, интервал ч, ставка] → сумма ставок за сутки UTC и наименьший интервал за сутки."""
    a = np.asarray(arr, np.float64)
    if not len(a):
        return pd.DataFrame(columns=["fsum", "fint", "fcnt"])
    d = (a[:, 0] // DAY) * DAY
    df = pd.DataFrame({"d": d, "r": a[:, 2], "i": a[:, 1]})
    g = df.groupby("d")
    return pd.DataFrame({"fsum": g.r.sum(), "fint": g.i.min(), "fcnt": g.r.size()})


def _zip_rows(path):
    """Месячный архив 1h-свечей спота Binance → строки [t, qv, tbq, n, c] (время свечи в сек)."""
    try:
        data = open(path, "rb").read()
        if not data:
            return []
        z = zipfile.ZipFile(io.BytesIO(data))
        txt = z.read(z.namelist()[0]).decode()
    except Exception:
        return []
    out = []
    for ln in txt.splitlines():
        p = ln.split(",")
        if len(p) < 11 or not p[0][:1].isdigit():
            continue
        t = int(p[0])
        t = t // 1000000 if t > 10 ** 14 else t // 1000
        out.append((t, float(p[7]), float(p[10]), float(p[8]), float(p[4])))
    return out


def spot_hourly(per):
    """{перп: массив [t, qv, tbq, n, c]} часовых свечей спота Binance (пара к USDT) за период."""
    src = PER[per]["spot"]
    if src.endswith(".pkl"):
        return pickle.load(open(src, "rb"))
    files = glob.glob(os.path.join(src, "monthly_klines_*_1h_*.zip"))
    by = {}
    for f in files:
        m = re.match(r"monthly_klines_(.+?)USDT_1h_", os.path.basename(f))
        if m:
            by.setdefault(m.group(1), []).append(f)
    out = {}
    for b, fs in by.items():
        rows = []
        for f in sorted(fs):
            rows += _zip_rows(f)
        if rows:
            out[b] = np.array(sorted(set(rows)))
    return out


def spot_daily(arr):
    a = np.asarray(arr, np.float64)
    d = (a[:, 0] // DAY) * DAY
    df = pd.DataFrame({"d": d, "sqv": a[:, 1], "stb": a[:, 2], "sn": a[:, 3], "sc": a[:, 4]})
    g = df.groupby("d")
    return pd.DataFrame({"sqv": g.sqv.sum(), "stb": g.stb.sum(), "sn": g.sn.sum(), "sc": g.sc.last()})


def kr_hourly(per):
    """Корейские часовые свечи рынков к воне: {биржа: {монета: {t, c, v}}} и функция курса воны за $ по часам."""
    cfg = PER[per]
    C = {}
    if cfg["kmap"] is None:                       # 2024–2026: s15/kr_candles_<биржа>.pkl с рынком USDT
        for ex in ("upbit", "bithumb"):
            C[ex] = pickle.load(open(f"{cfg['kc']}/kr_candles_{ex}.pkl", "rb"))
        rates = {}
        for ex in C:
            u = C[ex].get("USDT")
            if u is not None and len(u["t"]):
                rates[ex] = pd.Series(np.asarray(u["c"], float), index=np.asarray(u["t"], np.int64))
        return C, rates
    for ex in ("upbit", "bithumb"):
        C[ex] = {}
        for f in glob.glob(f"{cfg['kc']}/{ex}/KRW-*.pkl"):
            x = pickle.load(open(f, "rb"))
            if x and len(x.get("t", [])):
                C[ex][os.path.basename(f)[4:-4]] = x
    return C, None


def cmc_snapshots():
    """Дневные снимки CMC топ-200 (s136/raw): {сутки (сек): DataFrame[id, sym, rank, mcap, circ, price, vol]}."""
    out = {}
    for f in sorted(glob.glob(f"{D}/s136/raw/*.json")):
        day = ts(os.path.basename(f)[:-5])
        try:
            rows = json.load(open(f))
        except Exception:
            continue
        out[day] = pd.DataFrame(rows, columns=["id", "sym", "rank", "mcap", "circ", "price", "vol"])
    return out


def journals(per):
    """Входы журналов за период — только монета и время входа (для пересечений; доходы не читаются).
    🔝 s65, 👀 s83, ⏰ s88 (open9), 🛒 s49/s118 (доля спота ≥ 26%), 🔑⁺ s142, 🐋 s167lv (правило бота B, спокойный
    рынок ±5%), 🇰🇷 s118 (2020–2024) и s20 (2024–2026), 🇰🇷🆕 s20 (2024–2026)."""
    rows = []

    def add(j, df, cond=None):
        if df is None or not len(df):
            return
        x = df if cond is None else df[cond(df)]
        for s, t in zip(x["s"], x["t"]):
            s = s[:-4] if isinstance(s, str) and s.endswith("USDT") else s
            rows.append((j, s, int(t)))

    def rp(p, cols):
        if not os.path.exists(p):
            return None
        x = pd.read_pickle(p)
        return x[[c for c in cols if c in x.columns]]
    if per == "2024–2026":
        k20 = rp(f"{D}/s20/trades.pkl", ["s", "te", "journal"])          # 🇰🇷 и 🇰🇷🆕 бэктеста (s20)
        if k20 is not None:
            k20 = k20.rename(columns={"te": "t"})
            add("🇰🇷", k20, lambda x: x.journal == "🇰🇷")
            add("🇰🇷🆕", k20, lambda x: x.journal == "🇰🇷🆕")
        add("🔝", rp(f"{D}/s65/trades.pkl", ["s", "t"]))
        add("👀", rp(f"{D}/s83/trades.pkl", ["s", "t"]))
        add("⏰", rp(f"{D}/s88/trades.pkl", ["s", "t", "open9"]), lambda x: x.open9.astype(bool))
        add("🛒", rp(f"{D}/s49/trades.pkl", ["s", "t", "share"]), lambda x: x.share >= 0.26)
    elif per == "2022–2024":
        add("🔝", rp("/home/user/mc_oos/s65/trades.pkl", ["s", "t"]))
        add("⏰", rp(f"{D}/s88/oos_trades.pkl", ["s", "t", "open9"]), lambda x: x.open9.astype(bool))
        add("🛒", rp("/home/user/mc_oos/s118_spot.pkl", ["s", "t", "share"]), lambda x: x.share >= 0.26)
        add("🇰🇷", rp("/home/user/mc_oos/s118_kr.pkl", ["s", "t"]))
    else:
        add("⏰", rp(f"{D}/s88/oos2020_trades.pkl", ["s", "t", "open9"]), lambda x: x.open9.astype(bool))
        add("🛒", rp("/home/user/mc_2020/s118_spot2020.pkl", ["s", "t", "share"]), lambda x: x.share >= 0.26)
        add("🇰🇷", rp("/home/user/mc_2020/s118_kr.pkl", ["s", "t"]))
    add("🔑⁺", rp(f"{D}/s142_{per}.pkl", ["s", "t"]))
    add("🐋", rp(f"{D}/s167lv_{per}.pkl", ["s", "t", "B", "r24"]), lambda x: x.B.astype(bool) & (x.r24.abs() <= 0.05))
    J = pd.DataFrame(rows, columns=["j", "s", "t"])
    t0, t1 = ts(PER[per]["t0"]), ts(PER[per]["t1"])
    return J[(J.t >= t0 - 14 * DAY) & (J.t < t1 + 14 * DAY)].reset_index(drop=True)
