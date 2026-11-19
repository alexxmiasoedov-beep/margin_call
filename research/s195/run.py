"""s195 — «серийные заводы» (гипотеза и порог — ВЫВОДЫ.md, записаны до расчёта).

events: таблица событий по всем периодам → /home/user/mc_data/s195_events.pkl:
  - main — третий перевод новой серии (каждый ≥ 0,05% обращения, ≥ 1 ч между переводами, за 14 сут; отправитель без заводов
    токена на биржи за 90 сут до начала серии);
  - all — то же без условия «новый»; f01 — новая серия с переводами ≥ 0,1%;
  - ctl — первый завод нового отправителя (≥ 0,05%, нет его заводов этого токена на биржи за 90 сут).
  Время — точное время блока (кэш s160 + RPC). Вход — закрытие первой 15-мин свечи не раньше чем через 15 мин после блока.
<период>: сделки (шорт 7 сут, стоп 50%; запасной — 24 ч, стоп 25%), одна на монету за 7 сут (24 ч для запасного) по каждому
  виду → s195_<период>.pkl; хедж — индекс альтов s103, плацебо — та же монета за 45/90/135 сут.
report: сводка.
Запуск из /home/user/mc_data: python3 <repo>/research/s195/run.py events; [MC_K=… MC_F=…] … run.py <период>; … run.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s160"))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"


def controls(X, f=0.0005, new=90 * DAY):
    """Первый завод нового отправителя на Binance: ≥ f, у отправителя нет заводов токена на биржи за 90 сут до него."""
    B = X[(X.exch == "Binance") & (X.frac >= f)].sort_values("t")
    keys = set(zip(B.frm, B.tok))
    A = X[[(a, b) in keys for a, b in zip(X.frm, X.tok)]]
    allt = {k: np.sort(g.t.values) for k, g in A.groupby(["frm", "tok"], sort=False)}
    out = []
    for (frm, tok), g in B.groupby(["frm", "tok"], sort=False):
        a = allt[(frm, tok)]
        for r in g.itertuples():
            prior = a[(a < r.t) & (a >= r.t - new)]
            if len(prior) == 0:
                out.append(dict(frm=frm, tok=tok, perp=r.perp, t=r.t, block=r.block, frac=r.frac))
    return pd.DataFrame(out)


def block_times_saved(blocks):
    """Время блоков с кэшем s160: пакеты по 50 блоков в 2 потока, кэш сохраняется каждые 40 пакетов (прерванный сбор
    продолжается)."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    import events as EV  # noqa: E402  (s160)
    cache = EV._load(EV.BT_CACHE)
    todo = [b for b in blocks if str(b) not in cache]
    print("времён блоков к загрузке:", len(todo), "из", len(blocks), flush=True)

    def one(part):
        r = EV.post([{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [hex(b), False]}
                     for j, b in enumerate(part)])
        out = {}
        for x in r or []:
            if isinstance(x, dict) and x.get("result"):
                out[str(part[x["id"]])] = int(x["result"]["timestamp"], 16)
        return out
    for rnd in range(4):
        todo = [b for b in todo if str(b) not in cache]
        if not todo:
            break
        parts = [todo[i:i + 50] for i in range(0, len(todo), 50)]
        with ThreadPoolExecutor(2) as ex:
            for k, res in enumerate(ex.map(one, parts)):
                cache.update(res)
                if k % 40 == 39:
                    json.dump(cache, open(EV.BT_CACHE, "w"))
                    print(f"  проход {rnd}: пакетов {k + 1} из {len(parts)}", flush=True)
        json.dump(cache, open(EV.BT_CACHE, "w"))
    return {int(b): cache[str(b)] for b in blocks if str(b) in cache}


def events():
    import probe as P  # noqa: E402
    import events as EV  # noqa: E402  (s160)
    X = pd.read_pickle(f"{OUT}/s195_deposits.pkl")
    parts = []
    E = P.series(X, 0.0005)
    E["kind"] = np.where(E.newdep, "main", "")
    parts += [E[E.newdep].assign(kind="main"), E.assign(kind="all")]
    E1 = P.series(X, 0.001)
    parts.append(E1[E1.newdep].assign(kind="f01"))
    Cn = controls(X)
    parts.append(Cn.assign(kind="ctl"))
    Z = pd.concat(parts, ignore_index=True)
    # блок события у серий: перевод отправителя с этим (интерполированным) временем — номер блока из таблицы заводов
    first = X.sort_values("block").drop_duplicates(["frm", "tok", "t"]).set_index(["frm", "tok", "t"]).block
    need = Z.block.isna() if "block" in Z else pd.Series(True, index=Z.index)
    Z.loc[need, "block"] = first.reindex(pd.MultiIndex.from_arrays([Z.frm[need], Z.tok[need], Z.t[need]])).values
    Z.to_pickle(f"{OUT}/s195_events_raw.pkl")
    bt = block_times_saved(sorted(set(int(b) for b in Z.block.dropna())))
    Z["tb"] = Z.block.map(lambda b: bt.get(int(b), np.nan) if b == b else np.nan)
    print("событий по видам:", Z.groupby("kind").size().to_dict(), "| без времени блока:", int(Z.tb.isna().sum()))
    # завод ≥ 0,5% той же монеты за 48 ч до события (часть 🐋)
    big = X[(X.exch == "Binance") & (X.frac >= 0.005)]
    bigt = {k: np.sort(g.t.values) for k, g in big.groupby("perp")}
    Z["big48"] = [bool(len(bigt.get(p, []))) and bool(np.any((bigt[p] <= t) & (bigt[p] >= t - 48 * 3600)))
                  for p, t in zip(Z.perp, Z.t)]
    Z.to_pickle(f"{OUT}/s195_events.pkl")


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    Z = pd.read_pickle(f"{OUT}/s195_events.pkl").dropna(subset=["tb"])
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    Z = Z[(Z.tb >= t0) & (Z.tb < t1)].copy()
    Z["entry"] = (np.ceil((Z.tb + 900) / 900) * 900).astype(np.int64)       # закрытие свечи ≥ блок + 15 мин
    rows = []
    for (kind, s), g in Z.groupby(["kind", "perp"]):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        g = g.sort_values("entry")
        T = g.entry.values - 900
        I = np.searchsorted(t, T)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T) & (I >= 96)
        if not ok.any():
            continue
        g, I = g[ok].copy(), I[ok]
        lo, hi = FB.live(s)
        age_ok = t[I] >= lo + DAY                                        # фьючерс старше суток
        g, I = g[age_ok], I[age_ok]
        if not len(g):
            continue
        for hold, sl, col in ((168, 0.50, ""), (24, 0.25, "_24")):
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            keep = np.zeros(len(I), bool)
            last = -10 ** 12
            for j in range(len(I)):
                if okt[j] and t[I[j]] >= last + hold * 3600:              # одна сделка на монету за срок сделки
                    keep[j] = True
                    last = t[I[j]]
            mv = FB.alt_mv(t[I] + 900, tend)
            pl = FB.placebo(s, I, sl, hold, -1)
            g[f"net{col}"] = np.where(keep, net, np.nan)
            g[f"hed{col}"] = np.where(keep, net + mv, np.nan)
            g[f"stop{col}"] = np.where(keep, stp, False)
            g[f"pl{col}"] = np.where(keep, pl, np.nan)
        g["r24"] = c[I] / c[I - 96] - 1
        g["t_in"] = t[I] + 900
        rows.append(g)
    X = pd.concat(rows, ignore_index=True)
    X["per"] = per
    X.to_pickle(f"{OUT}/s195_{per}.pkl")
    print(per, X[X.net.notna()].groupby("kind").size().to_dict(), flush=True)


def report():
    import common182 as C  # noqa: E402
    pers = list(C.PER)
    print("s195 — «серийные заводы»: третий перевод новой серии на Binance → шорт перпа 7 сут, стоп 50%\n")
    parts_h, parts_d, ok_all = [], [], True
    for per in pers:
        X = pd.read_pickle(f"{OUT}/s195_{per}.pkl").rename(columns={"t": "t_dep"})
        X["t"] = X.t_in
        X["why"] = np.where(X.stop, "стоп", "время")
        print(f"== {per} ==")
        for kind, name in (("main", "основной: новая серия"), ("all", "все серии"), ("f01", "новая серия, переводы ≥ 0,1%"),
                           ("ctl", "контроль: первый завод нового отправителя")):
            x = X[(X.kind == kind) & X.net.notna()]
            print(f"  {name}: {C.line(x, per)}")
        x = X[(X.kind == "main") & X.net.notna()]
        y = X[(X.kind.isin(["main", "ctl"])) & X.net.notna()]
        d, se = C.diff(y.net, y.kind == "main", y.t)
        parts_d.append((d, se, len(x)))
        print(f"  Δ основной − контроль: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        parts_h.append((mh, abs(mh / th) if th else np.nan, n))
        cut = C.ts(C.PER[per][2])
        h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
        if per == "2024–2026":
            crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{a} — {'да' if b else 'НЕТ'}" for a, b in crit))
            ok_all &= all(b for _, b in crit)
        ok_all &= (m > 0) and (mh > 0)
        print("  разрезы основного:")
        x24 = X[(X.kind == "main") & X.net_24.notna()]
        mm, tt, nn = C.ct(x24.net_24, x24.t)
        print(f"    24 ч, стоп 25%: n={nn} {mm:+.2%} (t {tt:+.1f}), с хеджем {x24.hed_24.mean():+.2%}, сверх плацебо "
              f"{(x24.net_24 - x24.pl_24).mean():+.2%}")
        for nm, msk in (("без завода ≥ 0,5% за 48 ч (вне 🐋)", ~x.big48), ("с заводом ≥ 0,5% за 48 ч", x.big48),
                        ("набрано < 0,3%", x.cum < 0.003), ("набрано ≥ 0,3%", x.cum >= 0.003),
                        ("спокойный рынок |r24| ≤ 5%", x.r24.abs() <= 0.05), ("после хода |r24| > 5%", x.r24.abs() > 0.05)):
            z = x[msk]
            mm, tt, nn = C.ct(z.net, z.t)
            print(f"    {nm}: n={nn} {mm:+.2%} (t {tt:+.1f}), с хеджем {z.hed.mean():+.2%}, сверх плацебо {(z.net - z.pl).mean():+.2%}")
        print()
    m, t = C.combine(parts_h)
    md, td = C.combine(parts_d)
    ok_all &= (t >= 3) and (td >= 2)
    print(f"шесть лет с хеджем: {m:+.2%} (t {t:+.1f}); Δ к контролю вместе: {md:+.2%} (t {td:+.1f})")
    print("ИТОГ:", "порог пройден" if ok_all else "порог не пройден")


if __name__ == "__main__":
    a = sys.argv[1]
    events() if a == "events" else report() if a == "report" else run(a)
