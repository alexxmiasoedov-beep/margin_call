"""s289 — проверка гипотез s288 (канал Whale Alert) по записи ВЫВОДЫ.md (коммит 194c228).

Запуск из /home/user/mc_data:
  python3 -I <repo>/research/s289/run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 -I <repo>/research/s289/run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 -I <repo>/research/s289/run.py 2020–2022
  MC_K=s224/k_d.pkl MC_F=s224/fund_d.pkl python3 -I <repo>/research/s289/run.py свежий
  python3 -I <repo>/research/s289/run.py report
Сделки — /home/user/mc_data/s289_<период>.pkl, сводка — /home/user/mc_data/s289_report.txt."""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D0 = "/home/user/mc_data"
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19"), "свежий": ("2026-10-19", "2026-11-19")}
MAIN3 = ("2020–2022", "2022–2024", "2024–2026")
BAR, DAY, WEEK = 900, 86400, 7 * 86400
MONTH = 30.44 * DAY


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def entry(t):
    return (np.ceil((np.asarray(t, np.int64) + 60) / BAR) * BAR).astype(np.int64)


def thin(t, gap):
    t = np.sort(np.asarray(t, np.int64))
    keep, last = [], -10 ** 12
    for x in t:
        if x - last >= gap:
            keep.append(x)
            last = x
    return np.array(keep, np.int64)


def events(P, X0, fut_of):
    """Список событий: (hyp, var, T, coin, side, hold_h, sl). coin = 'basket' — корзина альтов."""
    ev = []

    def add(hyp, var, T, coin, side, hold, sl):
        for x in np.asarray(T, np.int64):
            ev.append((hyp, var, int(x), coin, side, hold, sl))
    tr = P.kind == "transfer"
    st = P.tic.isin(["USDT", "USDC"])
    iss = tr & st & (P.fe == "issuer") & P.te.isin(["cex", "unknown", "inst", "other"]) & (P.usd >= 1e8)
    usdc_m = (P.kind == "mint") & (P.tic == "USDC") & (P.usd >= 1e8)
    g1 = thin(entry(P[(iss & (P.swap != "возврат раньше")) | usdc_m].t), 3600)
    for coin in ("basket", "BTC"):
        add("Г1", "основное", g1, coin, 1, 4, 0.05)
    add("Г1", "контроль: смена сети", thin(entry(P[iss & (P.swap == "возврат раньше")].t), 3600), "basket", 1, 4, 0.05)
    add("Г1", "контроль: авторизация Tether", thin(entry(P[(P.kind == "mint") & (P.tic == "USDT")].t), 3600),
        "basket", 1, 4, 0.05)
    red = ((tr & st & (P.te == "issuer")) | ((P.kind == "burn") & st)) & (P.usd >= 1e8)
    add("Г1", "контроль: выкуп ≥ 100 млн $", thin(entry(P[red].t), 3600), "basket", 1, 4, 0.05)
    stb = tr & (P.cc == "stable") & ~P.tic.isin(["XAUT", "PAXG"])
    g2 = stb & (P.te == "cex") & ~P.fe.isin(["cex", "issuer"]) & (P.usd >= 1e8)
    for coin in ("basket", "BTC"):
        add("Г2", "основное", thin(entry(P[g2].t), 3600), coin, 1, 4, 0.05)
    add("Г2", "только Binance", thin(entry(P[g2 & (P.tn == "Binance")].t), 3600), "basket", 1, 4, 0.05)
    mir = stb & (P.fe == "cex") & ~P.te.isin(["cex", "issuer"]) & (P.usd >= 1e8)
    add("Г2", "зеркало: с бирж", thin(entry(P[mir].t), 3600), "basket", 1, 4, 0.05)
    for coin in ("BTC", "ETH"):
        m = tr & (P.tic == coin) & (P.te == "cex") & P.fe.isin(["unknown", "other"]) & (P.usd >= 5e7)
        add("Г3", f"основное {coin}", thin(entry(P[m].t), 7200), coin, -1, 8, 0.03)
        mo = tr & (P.tic == coin) & (P.fe == "cex") & P.te.isin(["unknown", "other"]) & (P.usd >= 5e7)
        add("Г3", f"зеркало: {coin} с бирж", thin(entry(P[mo].t), 7200), coin, -1, 8, 0.03)
        mi = tr & (P.tic == coin) & (P.te == "inst") & P.fe.isin(["unknown", "other"]) & (P.usd >= 5e7)
        add("Г3", f"контроль: {coin} в кастоди", thin(entry(P[mi].t), 7200), coin, -1, 8, 0.03)
    # Г5: суточный баланс стейблкоинов на биржах
    d = P.assign(day=(P.t // DAY).astype(int))
    sin = (stb & (d.te == "cex") & ~d.fe.isin(["cex", "issuer"])) * d.usd.fillna(0)
    sout = (stb & (d.fe == "cex") & ~d.te.isin(["cex", "issuer"])) * d.usd.fillna(0)
    net = (sin - sout).groupby(d.day).sum()
    full = net.reindex(range(int(net.index.min()), int(net.index.max()) + 1), fill_value=0.0)
    z = (full - full.rolling(30).mean().shift(1)) / full.rolling(30).std().shift(1)
    z = z[z.notna() & (z != 0)]
    for coin in ("basket", "BTC"):
        for sgn in (1, -1):
            T = (z[np.sign(z) == sgn].index.values + 1) * DAY
            add("Г5", "основное", T, coin, sgn, 24, 0.05)
            T = (z[(np.sign(z) == sgn) & (np.abs(z) >= 1)].index.values + 1) * DAY
            add("Г5", "|z| ≥ 1", T, coin, sgn, 24, 0.05)
    # Г4 (для отчёта): альт с перпом на биржу → шорт монеты, 8 ч, стоп 10%
    x = X0[X0.perp & X0.fe.isin(["unknown", "other"])]
    for tic, g in x.groupby("tic"):
        fs, mult = fut_of(str(tic))
        if fs:
            add("Г4", "основное", thin(entry(g.t), 8 * 3600), fs, -1, 8, 0.10)
    E = pd.DataFrame(ev, columns=["hyp", "var", "T", "coin", "side", "hold", "sl"])
    return E


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    from common import fut_of  # noqa: E402
    spec = importlib.util.spec_from_file_location("s287run", os.path.join(HERE, "..", "s287", "run.py"))
    R7 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R7)
    V = R7._mod("vs", os.path.join(HERE, "..", "s286", "study", "volstudy.py"))
    a, b = ts(WIN[per][0]), ts(WIN[per][1])
    P = pd.read_pickle(f"{D0}/s288/posts.pkl.gz")
    X0 = pd.read_pickle(f"{D0}/s288/alt_deposits.pkl.gz")
    E = events(P, X0, fut_of)
    E = E[(E["T"] >= a) & (E["T"] < b)].reset_index(drop=True)
    # Г3: спокойный рынок — |ход BTC за 24 ч до входа| ≤ 3%
    kb = FB.K["BTC"]
    tb, cb = kb["t"].astype(np.int64), kb["c"].astype(float)

    def px(T):
        k = np.searchsorted(tb, np.asarray(T, np.int64) - BAR)
        ok = (k < len(tb)) & (tb[np.minimum(k, len(tb) - 1)] == np.asarray(T, np.int64) - BAR)
        return np.where(ok, cb[np.minimum(k, len(tb) - 1)], np.nan)
    r24 = px(E["T"].values) / px(E["T"].values - DAY) - 1
    calm = np.abs(r24) <= 0.03
    E = E[(E.hyp != "Г3") | calm].reset_index(drop=True)
    E["eid"] = np.arange(len(E))
    # корзина — 50 крупнейших альтов на сутки входа
    D = R7.load_D(V, FB.K, *WIN[per])
    rows = []
    for k in range(len(E)):
        r = E.iloc[k]
        if r.coin == "basket":
            dd = R7.i_of(D, int(r["T"]) - BAR) // 96
            if dd < 0 or dd >= D["nd"]:
                continue
            top = D["top"][dd]
            for j in top[top >= 0]:
                rows.append((r.eid, D["coins"][j], int(r["T"]), int(r.side), float(r.hold), float(r.sl)))
        else:
            rows.append((r.eid, r.coin, int(r["T"]), int(r.side), float(r.hold), float(r.sl)))
    del D
    L = pd.DataFrame(rows, columns=["eid", "s", "T", "side", "hold", "sl"])
    out = []
    for (s, side, hold, sl), g in L.groupby(["s", "side", "hold", "sl"]):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        T = g["T"].to_numpy(np.int64)
        I = np.searchsorted(t, T - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T - BAR)
        if not ok.any():
            continue
        g, I = g[ok], I[ok]
        okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, int(side))
        pl = FB.placebo(s, I, sl, hold, int(side), days=(7, 14, 21))
        alt = FB.alt_mv(t[I] + BAR, np.where(okt, tend, t[I] + BAR))
        for e, ok1, n1, s1, p1, a1 in zip(g.eid.values, okt, net, stp, pl, alt):
            if ok1:
                out.append((e, s, float(n1), bool(s1), float(p1), float(n1 - side * a1)))
    Tr = pd.DataFrame(out, columns=["eid", "s", "net", "stop", "pl", "hed"])
    agg = Tr.groupby("eid").agg(net=("net", "mean"), pl=("pl", "mean"), stop=("stop", "mean"), hed=("hed", "mean"),
                                n=("net", "size"))
    R = E.set_index("eid").join(agg, how="inner").reset_index()
    R["per"] = per
    R.to_pickle(f"{D0}/s289_{per}.pkl")
    print(per, "событий со сделками", R.groupby(["hyp", "var", "coin"]).size().to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float)
    w = np.asarray(t, np.int64) // WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    R = pd.concat([pd.read_pickle(f"{D0}/s289_{p}.pkl") for p in WIN if os.path.exists(f"{D0}/s289_{p}.pkl")],
                  ignore_index=True)
    lines = []

    def P_(s):
        lines.append(s)
        print(s)
    groups = [("Г1", "основное", "basket", True), ("Г1", "основное", "BTC", False),
              ("Г1", "контроль: смена сети", "basket", False), ("Г1", "контроль: авторизация Tether", "basket", False),
              ("Г1", "контроль: выкуп ≥ 100 млн $", "basket", False),
              ("Г2", "основное", "basket", True), ("Г2", "основное", "BTC", False),
              ("Г2", "только Binance", "basket", False), ("Г2", "зеркало: с бирж", "basket", False),
              ("Г3", "основное", None, True), ("Г3", "основное BTC", "BTC", False), ("Г3", "основное ETH", "ETH", False),
              ("Г3", "зеркало: BTC с бирж", "BTC", False), ("Г3", "зеркало: ETH с бирж", "ETH", False),
              ("Г3", "контроль: BTC в кастоди", "BTC", False), ("Г3", "контроль: ETH в кастоди", "ETH", False),
              ("Г5", "основное", "basket", True), ("Г5", "основное", "BTC", False), ("Г5", "|z| ≥ 1", "basket", False),
              ("Г4", "основное", None, False)]
    for hyp, var, coin, main in groups:
        if hyp == "Г3" and var == "основное":
            sel = R[(R.hyp == "Г3") & R["var"].str.startswith("основное")]
            name = "Г3 BTC и ETH на биржу → шорт той же монеты (основная)"
        elif hyp == "Г4":
            sel = R[R.hyp == "Г4"]
            name = "Г4 альт на биржу → шорт монеты 8 ч (для отчёта; с хеджем — столбец hed)"
        else:
            sel = R[(R.hyp == hyp) & (R["var"] == var) & (R.coin == coin)]
            name = f"{hyp} {var}, {'корзина альтов' if coin == 'basket' else coin}{' (основная)' if main else ''}"
        P_(f"\n### {name}")
        signs, allx = [], []
        for p in WIN:
            x = sel[sel.per == p]
            mo = (ts(WIN[p][1]) - ts(WIN[p][0])) / MONTH
            m, t, n = ct(x.net, x["T"])
            if n < 5:
                P_(f"  {p}: n={n}")
                if p in MAIN3:
                    signs.append(False)
                continue
            md, td, _ = ct(x.net - x.pl, x["T"])
            mh, th, _ = ct(x.hed, x["T"])
            mid = float(np.median(x["T"]))
            h1, h2 = x[x["T"] < mid].net.mean(), x[x["T"] >= mid].net.mean()
            P_(f"  {p}: n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
               f"сверх плацебо {md:+.2%} (t {td:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f}); стопов {x.stop.mean():.0%}")
            if p in MAIN3:
                signs.append(m > 0)
                allx.append(x)
            if main and p == "2024–2026":
                conds = (("≥ 20 в мес.", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                         ("сверх плацебо > 0", md > 0))
                P_("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds))
        if allx:
            A = pd.concat(allx)
            m, t, n = ct(A.net, A["T"])
            tail = (f"; плюс во всех — {'да' if all(signs) and len(signs) == 3 else 'нет'} → " +
                    ("ПОРОГ ТРЁХ ПЕРИОДОВ ПРОЙДЕН" if all(signs) and len(signs) == 3 and t >= 3 else "не пройден")) if main else ""
            P_(f"  вместе (три периода): {m:+.2%} (t {t:+.1f}, n={n}){tail}")
    open(f"{D0}/s289_report.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
