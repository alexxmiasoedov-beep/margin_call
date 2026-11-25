"""s288 — частоты гипотез Г1–Г5 (ВЫВОДЫ.md, «Гипотезы») по трём периодам и свежему отрезку. Только счёт событий;
фильтр «спокойного рынка» — ход BTC за 24 ч ДО входа (условие правила, не доход). Направленные доходы НЕ считаются.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/hyp_freq.py → s288/hyp_freq.txt"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

BAR = 900
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def btc_close():
    """15-мин закрытия BTC по всем файлам свечей: время открытия → закрытие."""
    out = {}
    for f in ("s117/k_2020.pkl", "s117/k_oos.pkl", "s2/k2y.pkl", "s224/k_d.pkl"):
        K = pickle.load(open(f, "rb"))
        a = K["BTC"]
        for t, c, q in zip(np.asarray(a["t"], np.int64), np.asarray(a["c"], float), np.asarray(a["qv"], float)):
            if q > 0:
                out[int(t)] = c
        del K
    s = pd.Series(out).sort_index()
    return s


def thin(t, gap):
    t = np.sort(np.asarray(t, np.int64))
    keep, last = [], -10 ** 12
    for x in t:
        if x - last >= gap:
            keep.append(x)
            last = x
    return np.array(keep, np.int64)


def r24(B, T):
    """Ход BTC за 24 ч до входа T (вход — закрытие свечи, открытой в T − 15 мин)."""
    i1 = B.index.searchsorted(T - BAR, "right") - 1
    i0 = B.index.searchsorted(T - BAR - 86400, "right") - 1
    ok = (i1 >= 0) & (i0 >= 0)
    v = np.full(len(T), np.nan)
    v[ok] = B.values[i1[ok]] / B.values[i0[ok]] - 1
    return v


def line(name, T):
    T = np.asarray(T, np.int64)
    per = C.period_of(T)
    return name + ": " + " / ".join(f"{(per == p).sum() / C.months(p):.1f}" for p in C.PER)


def main():
    P = pd.read_pickle(f"{C.OUT}/posts.pkl.gz")
    P = P[P.per.notna()]
    B = btc_close()
    entry = lambda t: (np.ceil((np.asarray(t, np.int64) + 1) / BAR) * BAR).astype(np.int64)  # noqa: E731
    say("Частоты в месяц: 2020–2022 / 2022–2024 / 2024–2026 / свежий 19.10–25.11.2026")
    tr = P.kind == "transfer"
    st = P.tic.isin(["USDT", "USDC"])
    # Г1: выпуск стейблкоина — из казны эмитента в обращение (биржа, ОТС, неизвестный) или чеканка USDC; ≥ 100 млн $
    iss = tr & st & (P.fe == "issuer") & P.te.isin(["cex", "unknown", "inst", "other"]) & (P.usd >= 1e8)
    usdc_m = (P.kind == "mint") & (P.tic == "USDC") & (P.usd >= 1e8)
    g1 = thin(entry(P[iss | usdc_m].t), 3600)
    say("\nГ1 выпуск стейблкоина ≥ 100 млн $ (одно событие на 60 мин)")
    say("  " + line("все", g1))
    say("  " + line("только казна → биржа", thin(entry(P[iss & (P.te == "cex")].t), 3600)))
    say("  " + line("только USDT из Tether Treasury", thin(entry(P[iss & (P.tic == "USDT")].t), 3600)))
    say("  " + line("без смены сети, видимой к моменту поста (основное)", thin(entry(P[(iss & (P.swap != "возврат раньше")) | usdc_m].t), 3600)))
    say("  " + line("контроль: смена сети (возврат в казну в другой сети раньше)", thin(entry(P[iss & (P.swap == "возврат раньше")].t), 3600)))
    say("  " + line("чеканка USDC", thin(entry(P[usdc_m].t), 3600)))
    say("  " + line("≥ 500 млн $", thin(entry(P[(iss | usdc_m) & (P.usd >= 5e8)].t), 3600)))
    say("  " + line("контроль: авторизация Tether (чеканка USDT в казну)", thin(entry(P[(P.kind == "mint") & (P.tic == "USDT")].t), 3600)))
    red = (tr & st & (P.te == "issuer")) | ((P.kind == "burn") & st)
    say("  " + line("зеркало: выкуп (→ казна, сжигание) ≥ 100 млн $", thin(entry(P[red & (P.usd >= 1e8)].t), 3600)))
    say("  " + line("все без порога 100 млн $", thin(entry(P[(tr & st & (P.fe == 'issuer') & P.te.isin(['cex', 'unknown', 'inst', 'other'])) | ((P.kind == 'mint') & (P.tic == 'USDC'))].t), 3600)))
    # Г2: стейблкоин на Binance от небиржевого адреса ≥ 100 млн $
    stb = tr & (P.cc == "stable") & ~P.tic.isin(["XAUT", "PAXG"])
    g2 = stb & (P.te == "cex") & (P.tn == "Binance") & (P.fe != "cex") & (P.fe != "issuer") & (P.usd >= 1e8)
    say("\nГ2 стейблкоин → Binance ≥ 100 млн $ (одно событие на 60 мин)")
    say("  " + line("все", thin(entry(P[g2].t), 3600)))
    say("  " + line("≥ 250 млн $", thin(entry(P[g2 & (P.usd >= 2.5e8)].t), 3600)))
    say("  " + line("контроль: стейблкоин ← Binance ≥ 100 млн $", thin(entry(P[stb & (P.fe == 'cex') & (P.fn == 'Binance') & (P.te != 'cex') & (P.usd >= 1e8)].t), 3600)))
    say("  " + line("контроль: стейблкоин → другие биржи ≥ 100 млн $", thin(entry(P[stb & (P.te == 'cex') & (P.tn != 'Binance') & ~P.fe.isin(['cex', 'issuer']) & (P.usd >= 1e8)].t), 3600)))
    say("  " + line("без порога", thin(entry(P[stb & (P.te == "cex") & (P.tn == "Binance") & ~P.fe.isin(["cex", "issuer"])].t), 3600)))
    g2all = stb & (P.te == "cex") & ~P.fe.isin(["cex", "issuer"]) & (P.usd >= 1e8)
    say("  " + line("все биржи ≥ 100 млн $ (основное)", thin(entry(P[g2all].t), 3600)))
    say("  " + line("все биржи, только от unknown", thin(entry(P[g2all & (P.fe == 'unknown')].t), 3600)))
    say("  " + line("контроль: стейблкоин ← все биржи ≥ 100 млн $", thin(entry(P[stb & (P.fe == 'cex') & ~P.te.isin(['cex', 'issuer']) & (P.usd >= 1e8)].t), 3600)))
    # Г3: BTC (ETH) на биржу от небиржевого адреса ≥ 50 млн $, спокойный рынок (|ход BTC за 24 ч| ≤ 3%)
    for coin in ("BTC", "ETH"):
        m = tr & (P.tic == coin) & (P.te == "cex") & P.fe.isin(["unknown", "other"]) & (P.usd >= 5e7)
        T = thin(entry(P[m].t), 7200)
        rr = r24(B, T)
        say(f"\nГ3 {coin} → биржи ≥ 50 млн $ (одно событие на 2 ч)")
        say("  " + line("все", T))
        say("  " + line("спокойный рынок |ход BTC за 24 ч| ≤ 3%", T[np.abs(rr) <= 0.03]))
        say("  " + line("только Binance, спокойный рынок", (lambda U: U[np.abs(r24(B, U)) <= 0.03])(thin(entry(P[m & (P.tn == 'Binance')].t), 7200))))
        mo = tr & (P.tic == coin) & (P.fe == "cex") & P.te.isin(["unknown", "other"]) & (P.usd >= 5e7)
        U = thin(entry(P[mo].t), 7200)
        say("  " + line("контроль: с бирж, спокойный рынок", U[np.abs(r24(B, U)) <= 0.03]))
        mi = tr & (P.tic == coin) & (P.te == "inst") & P.fe.isin(["unknown", "other"]) & (P.usd >= 5e7)
        U = thin(entry(P[mi].t), 7200)
        say("  " + line("контроль: в кастоди (Coinbase Inst. и др.), спокойный рынок", U[np.abs(r24(B, U)) <= 0.03]))
    # Г3 вместе: BTC и ETH, каждая монета своей сделкой
    TT = []
    for coin in ("BTC", "ETH"):
        m = tr & (P.tic == coin) & (P.te == "cex") & P.fe.isin(["unknown", "other"]) & (P.usd >= 5e7)
        T = thin(entry(P[m].t), 7200)
        TT += list(T[np.abs(r24(B, T)) <= 0.03])
    say("\nГ3 вместе BTC + ETH, спокойный рынок: " + line("", np.array(TT, np.int64))[2:])
    # Г4: крупный альт с перпом от небиржевого адреса на любую биржу → шорт монеты (одно событие на монету за 8 ч)
    X0 = pd.read_pickle(f"{C.OUT}/alt_deposits.pkl.gz")
    X0 = X0[X0.perp]
    say("\nГ4 альт с перпом → биржи (от unknown и прочих, одно событие на монету за 8 ч)")
    for nm, m in (("все", X0.fe.isin(["unknown", "other"])),
                  ("≥ 10 млн $", X0.fe.isin(["unknown", "other"]) & (X0.usd >= 1e7)),
                  ("только Binance", X0.fe.isin(["unknown", "other"]) & (X0.dest == "Binance")),
                  ("контроль: от кастоди и ОТС", X0.fe == "inst")):
        T = []
        for _, g in X0[m].groupby("tic"):
            T += list(thin(entry(g.t), 8 * 3600))
        say("  " + line(nm, np.array(T, np.int64)))
    xo = P[(P.kind == "transfer") & (P.cc == "alt") & P.perp & (P.fe == "cex") & P.te.isin(["unknown", "other"])]
    T = []
    for _, g in xo.groupby("tic"):
        T += list(thin(entry(g.t), 8 * 3600))
    say("  " + line("контроль: альт с перпом ← биржи", np.array(T, np.int64)))
    say("  монеты (2024–2026): " + ", ".join(f"{k}:{v}" for k, v in X0[X0.fe.isin(['unknown', 'other']) & (X0.per == '2024–2026')].tic.value_counts().head(12).items()))
    # 🐋 вне Ethereum — альт с перпом от небиржевого адреса на Binance, цепь не Ethereum (отброшено по частоте)
    X = pd.read_pickle(f"{C.OUT}/alt_deposits.pkl.gz")
    X = X[X.perp & (X.dest == "Binance")]
    for nm, m in (("цепь не Ethereum, все", X.chain != "ethereum"),
                  ("цепь не Ethereum, ≥ 0,1% обращения", (X.chain != "ethereum") & (X.frac >= 0.001)),
                  ("цепь не Ethereum, ≥ 0,5% обращения", (X.chain != "ethereum") & (X.frac >= 0.005)),
                  ("цепь не Ethereum, ≥ 5% оборота CMC за 24 ч", (X.chain != "ethereum") & (X.lam >= 0.05)),
                  ("Ethereum (для сравнения с 🐋), ≥ 0,5% обращения", (X.chain == "ethereum") & (X.frac >= 0.005))):
        x = X[m]
        T = []
        for _, g in x.groupby("tic"):
            T += list(thin(entry(g.t), 48 * 3600))
        if nm.startswith("цепь не Ethereum, все"):
            say("\nОтброшено: 🐋 вне Ethereum по каналу (одно событие на монету за 48 ч)")
        say("  " + line(nm, np.array(T, np.int64)))
    # Г5: суточный баланс потоков канала (стейблкоины на биржи минус с бирж) — расчёт раз в сутки в 00:00 UTC
    say("\nГ5 суточный баланс канала: в месяц — 30,4 по построению (одна сделка в сутки); с порогом |z| ≥ 1 к 30 сут:")
    d = P.copy()
    d["day"] = (d.t // 86400).astype(int)
    sin = (stb & (d.te == "cex") & ~d.fe.isin(["cex", "issuer"])) * d.usd
    sout = (stb & (d.fe == "cex") & ~d.te.isin(["cex", "issuer"])) * d.usd
    net = (sin - sout).groupby(d.day).sum()
    full = net.reindex(range(net.index.min(), net.index.max() + 1), fill_value=0.0)
    z = (full - full.rolling(30).mean().shift(1)) / full.rolling(30).std().shift(1)
    T = (z[z.notna()].index.values + 1) * 86400
    say("  " + line("каждый день по знаку z (основное)", T))
    for k in (0.5, 1.0, 1.5):
        T = (z[np.abs(z) >= k].index.values + 1) * 86400
        say("  " + line(f"дней с |z| ≥ {k}", T))
    say("\nОтброшенные семьи (в месяц):")
    tx = P.text.fillna("")
    for nm, m in (("пробуждение старого адреса (dormant)", P.kind == "dormant"),
                  ("украденное (stolen funds, взломы)", (P.kind == "stolen") | P.fe.eq("hack")),
                  ("разлок и блокировка XRP (escrow)", P.kind.isin(["unlock", "escrow"])),
                  ("стейкинг и выход из стейкинга SOL", P.kind.isin(["stake", "unstake"])),
                  ("заморозка адреса (frozen)", P.kind == "frozen"),
                  ("авторизация Tether (чеканка USDT)", (P.kind == "mint") & (P.tic == "USDT")),
                  ("BTC в кастоди и из кастоди (Coinbase Inst. и др.)", tr & (P.tic == "BTC") & ((P.te == "inst") | (P.fe == "inst")))):
        say("  " + line(nm, entry(P[m].t)))
    open(f"{C.OUT}/hyp_freq.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
