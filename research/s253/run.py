"""s253 — Г1 «🐋 без спота» на Ethereum (гипотеза s252, раздел 6 отчёта; правило проверки — ВЫВОДЫ.md, записано до
расчёта). Заводы — s160_events.pkl (переводы ERC-20 ≥ 0,5% обращения CMC на адреса бирж от не-бирж, 10.2020–11.2026);
спот Binance — s252/spot_dates.json и часовые свечи спота s23/spot1h.pkl; состав индекса — снимок s252/nospot.json
(23.11.2026). Сделка — как у 🐋 (s221/run.py: вход на закрытии первой 15-мин свечи не раньше чем через 15 мин после
блока, ход перпа за 24 ч ±5%, перп старше суток, шорт 24 ч, стоп +25%, комиссия и фандинг; хедж индексом альтов;
плацебо той же монеты за 45/90/135 сут).

Запуск из /home/user/mc_data:
  python3 <repo>/research/s253/run.py count          — только число событий (без доходов)
  python3 <repo>/research/s253/run.py main           — 2024–2026 гг. (свечи s2/k2y.pkl)
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 <repo>/research/s253/run.py old   — 2022–2024 гг. (для отчёта)
"""
import importlib.util
import json
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s221", "s187", "s182", "s213"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
spec = importlib.util.spec_from_file_location("s221run", os.path.join(HERE, "..", "s221", "run.py"))
S221 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S221)

DAY, GAP, BIG, CALM = 86400, 48 * 3600, 0.005, 0.05
PER = {"2024–2026": ("2024-10-01", "2026-10-19", "2025-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01")}
IDX = {"Gate.io", "MEXC", "KuCoin", "Bitget", "Bybit", "OKX", "Coinbase"}      # спот CEX из индексов перпов без спота (s252)
CONS2EX = {"gateio": "Gate.io", "mexc": "MEXC", "bitget": "Bitget", "bybit": "Bybit", "okex": "OKX", "kucoin": "KuCoin",
           "coinbase": "Coinbase", "bitfinex": "Bitfinex"}
SKIP = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD",
        "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "BTCDOM", "DEFI"}           # стейблкоины, металлы, индексы (BL_SKIP бота)


OLD_SPOT = {"RENDER": 1635724800}       # спот под прежним тикером (архив data.binance.vision: RNDRUSDT с 11.2021)


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    return m.group(2) if m and not m.group(2)[0].isdigit() else fs


def spot_start(perps):
    """Первое появление спота Binance у монеты: первая дневная свеча пар монеты (s252) и первая часовая свеча с оборотом
    в s23/spot1h.pkl (ловит монеты, чей спот потом сняли). None — спота не было."""
    SD = json.load(open("s252/spot_dates.json"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    out = {}
    for p in perps:
        c = [SD.get(base(p)), SD.get(p)]
        for k in {p, base(p)}:
            a = SP.get(k)
            if a is not None and len(a) and (a[:, 1] > 0).any():
                c.append(float(a[a[:, 1] > 0, 0].min()))
        if p in OLD_SPOT:
            c.append(OLD_SPOT[p])
        c = [float(x) for x in c if x]
        out[p] = min(c) if c else None
    return out


def first48(df):
    keep, last = [], {}
    for r in df.itertuples():
        keep.append(not (r.perp in last and r.t - last[r.perp] < GAP))
        if keep[-1]:
            last[r.perp] = r.t
    return np.array(keep, bool)


def newdep(X):
    """«Новый вкладчик»: у адреса пополнения (frm) не было другого завода этой монеты ≥ 0,1% обращения за 7 сут до
    (таблица заводов s195, все биржи). Время в s195 приближённое, поэтому окно — по номерам блоков (7 сут ≈ 50 400
    блоков по 12 с), сам завод исключается по хешу транзакции."""
    D = pd.read_pickle("s195_deposits.pkl")
    D = D[D.frac >= 0.001][["frm", "perp", "block", "tx"]]
    D["frm"] = D.frm.str.lower()
    idx = {k: (g.block.values.astype(np.int64), g.tx.values) for k, g in D.groupby(["frm", "perp"])}
    out = []
    for r in X.itertuples():
        bb, tx = idx.get((str(r.frm).lower(), r.perp), (np.zeros(0, np.int64), np.zeros(0, object)))
        prev = (bb >= r.block - 50400) & (bb <= r.block) & (tx != r.tx)
        out.append(not prev.any())
    return np.array(out, bool)


def events():
    """Все заводы ≥ 0,5% от не-бирж на биржи кроме Binance у перпов без спота Binance на момент завода; класс (а) / (б)."""
    E = pd.read_pickle("s160_events.pkl")
    E = E[E.perp.notna() & (E.frac >= BIG) & (E.exch != "Binance")].copy()
    E = E[~E.perp.map(base).isin(SKIP)]
    FX = {x["symbol"][:-4]: x for x in json.load(open("s252/exinfo.json"))["symbols"] if x["symbol"].endswith("USDT")}
    coin = lambda p: p not in FX or (FX[p]["contractType"] == "PERPETUAL" and FX[p].get("underlyingType") == "COIN")  # noqa: E731
    E = E[E.perp.map(coin)]                                                         # без TradFi (акции, сырьё), индексов
    E["t"] = E.t.astype(np.int64)
    ss = spot_start(E.perp.unique())
    E["spot0"] = E.perp.map(ss)
    E = E[[pd.isna(s) or t < s for s, t in zip(E.spot0, E.t)]].copy()           # спота Binance ещё нет (NaN — не было)
    NS = {k[:-4]: v["cons"] for k, v in json.load(open("s252/nospot.json")).items()}
    E["snap"] = E.perp.isin(NS)                                                     # перп без спота и по снимку 23.11.2026
    w = []
    for r in E.itertuples():
        if r.snap:
            w.append(sum(c["weight"] for c in NS[r.perp] if CONS2EX.get(c["exchange"]) == r.exch))
        else:
            w.append(np.nan)
    E["w"] = w
    E["cls"] = np.where(E.snap, np.where(E.w > 0, "а", "б"), np.where(E.exch.isin(IDX), "а", "б"))
    E["clean"] = ~E.from_exch.fillna(False).astype(bool)                          # без перекладки (как s160, s252)
    return E.sort_values(["perp", "t"])


def pick(E, cls, clean=True):
    """Первое у монеты за 48 ч внутри класса; clean — сначала убрать перекладки."""
    X = E[(E.cls == cls) & (E.clean if clean else True)].sort_values(["perp", "t"])
    X = X[X.t != X.t.shift().where(X.perp == X.perp.shift())]                     # тот же блок — то же событие
    return X[first48(X)].copy()


def calm_share(X):
    import fastbt as FB  # noqa: E402
    ok = []
    for r in X.itertuples():
        a = FB.K.get(r.perp)
        if a is None:
            ok.append(np.nan); continue
        t = a["t"].astype(np.int64); te = int(np.ceil((r.t + 900) / 900) * 900); i = np.searchsorted(t, te - 900)
        if i >= len(t) or t[i] != te - 900 or i < 96:
            ok.append(np.nan); continue
        ok.append(float(abs(a["c"][i] / a["c"][i - 96] - 1) <= CALM))
    return np.array(ok)


def count():
    E = events()
    print("заводов ≥ 0,5% на биржи кроме Binance у перпов без спота Binance на момент завода:", len(E), "| перпов",
          E.perp.nunique(), "| по снимку без спота:", int(E.snap.sum()))
    for per, (a, b, _) in PER.items():
        mo = (ts(b) - ts(a)) / (30.44 * DAY)
        for cls in ("а", "б"):
            for clean in (True, False):
                X = pick(E, cls, clean)
                X = X[(X.t >= ts(a)) & (X.t < ts(b))]
                cs = calm_share(X) if per == "2024–2026" else np.full(len(X), np.nan)
                print(f"  {per} класс ({cls}) {'без перекладки' if clean else 'с перекладкой'}: {len(X)} ({len(X) / mo:.1f} в месяц), "
                      f"перпов {X.perp.nunique()}, по снимку {int(X.snap.sum())}"
                      + (f", спокойный рынок {np.nansum(cs):.0f} ({np.nansum(cs) / mo:.1f} в месяц)" if per == "2024–2026" else ""))
    X = pick(E, "а")
    X = X[(X.t >= ts("2024-10-01")) & (X.t < ts("2026-10-19"))]
    print("биржи (а):", X.exch.value_counts().to_dict())
    print("по месяцам (а):", X.t.map(lambda t: pd.Timestamp(t, unit="s").strftime("%Y-%m")).value_counts().sort_index().to_dict())


def line(x, per):
    if len(x) < 5:
        return f"n={len(x)}"
    a, b, mid = PER[per]
    mo = (ts(b) - ts(a)) / (30.44 * DAY)
    m, t, n = S221.ct(x.net, x.entry); mh, th, _ = S221.ct(x.hed, x.entry); md, td, _ = S221.ct(x.net - x.pl, x.entry)
    h1, h2 = x[x.entry < ts(mid)].net.mean(), x[x.entry >= ts(mid)].net.mean()
    return (f"n={n} ({n / mo:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
            f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}")


def run(per):
    a, b, mid = PER[per]
    E = events()
    out = {}
    for cls in ("а", "б"):
        for clean in (True, False):
            X = pick(E, cls, clean)
            X = X[(X.t >= ts(a)) & (X.t < ts(b))]
            if not len(X):
                continue
            X["new"] = newdep(X)
            R = S221.trades(X[["perp", "t", "block", "amt", "frac", "exch", "frm", "snap", "w", "new"]].copy())
            out[(cls, clean)] = R
    pd.to_pickle(out, f"s253_{per}.pkl")
    A, B = out[("а", True)], out.get(("б", True))
    calm = lambda R: R[R.net.notna() & (R.r24.abs() <= CALM)]                     # noqa: E731
    x = calm(A)
    print(f"s253 — {per}\n")
    print(f"Г1 основная — класс (а), без перекладки, спокойный рынок: {line(x, per)}")
    if per == "2024–2026":
        m, t, n = S221.ct(x.net, x.entry); mh, _, _ = S221.ct(x.hed, x.entry); md = (x.net - x.pl).mean()
        print("порог s253: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                         (("среднее > 0 и t ≥ 2 по неделям", m > 0 and t >= 2), ("с хеджем > 0", mh > 0),
                                          ("сверх плацебо > 0", md > 0))))
        h1, h2 = x[x.entry < ts(mid)].net.mean(), x[x.entry >= ts(mid)].net.mean()
        mo = (ts(b) - ts(a)) / (30.44 * DAY)
        print("правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                                (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                                                 ("сверх плацебо > 0", md > 0))))
    print("\nРазрезы (записаны до расчёта):")
    if B is not None:
        y = calm(B)
        print(f"  Г2 класс (б) — биржи вне индекса: {line(y, per)}")
        z = pd.concat([x.assign(d=1.0), y.assign(d=0.0)], ignore_index=True)
        d, se = diff_w(z.net, z.d, z.entry)
        print(f"  Г2 разница (а) − (б): {d:+.2%} (t {d / se:+.1f})" if np.isfinite(se) and se > 0 else "  Г2 разница: мало сделок")
    print(f"  новый вкладчик: {line(x[x.new], per)}")
    print(f"  повторный вкладчик: {line(x[~x.new], per)}")
    print(f"  вес биржи ≥ 0,2 (перпы снимка): {line(x[x.w >= 0.2], per)}")
    print(f"  вес биржи < 0,2 (перпы снимка): {line(x[x.w < 0.2], per)}")
    print(f"  перпы без спота по снимку 23.11.2026: {line(x[x.snap.astype(bool)], per)}")
    print(f"  предспотовые и снятые перпы: {line(x[~x.snap.astype(bool)], per)}")
    print(f"  доля ≥ 1%: {line(x[x.frac >= 0.01], per)}")
    print(f"  без фильтра рынка: {line(A[A.net.notna()], per)}")
    print(f"  с перекладкой (все переводы, как 🐋): {line(calm(out[('а', False)]), per)}")
    print(f"  🐋ᵛ λ ≥ 0,05: {line(x[x.lam >= 0.05], per)}")
    if per == "2024–2026":
        W = pd.read_pickle("s199_main_2024–2026.pkl")
        W = W[W.net.notna() & (W.r24.abs() <= CALM)]
        print(f"\nДля сравнения — s199 (заводы на другие биржи у всех монет, спокойный рынок): {line(W, per)}")


def diff_w(y, d, t):
    """Разность средних с ошибкой, кластеризованной по неделям входа."""
    y = np.asarray(y, float); d = np.asarray(d, float); t = np.asarray(t, float)
    m = ~np.isnan(y); y, d, t = y[m], d[m], t[m]
    if d.sum() < 5 or (1 - d).sum() < 5:
        return np.nan, np.nan
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    g = S221.wk(t)
    S = pd.DataFrame(Z * u[:, None]).groupby(g).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    if mode == "count":
        count()
    elif mode == "main":
        run("2024–2026")
    elif mode == "old":
        run("2022–2024")
