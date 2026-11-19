"""s183 — недельные признаки поперечного среза на понедельник 00:00 UTC (только данные строго до среза).

Запуск: python3 -I features.py <период>      Итог: /home/user/mc_data/s183/feat_<период>.pkl

Признаки (окна — полные сутки UTC до среза; «рынок» m — равновесный индекс альтов: средняя дневная лог-доходность
ликвидных альтов, оборот перпа за 7 сут ≥ 5 млн $ в сутки, возраст ≥ 30 сут, без BTC и ETH):
  цена:   r1, r7, r14, r28 (лог-доходности), r28s (2–4 нед. назад: d−29 … d−8), r90, dhi90 (к максимуму закрытий 90 сут),
          cgo60 (лог цены к VWAP 60 сут по типичной цене, «прибыль держателей», Grinblatt–Han), lprice;
  риск:   vol28 (ст. откл. дневных), rvol7 (из 15-мин), beta28, dbeta28 (бета на днях падения рынка), ivol28 (остаток),
          skew28, max7, max28 (наибольшая дневная доходность), rsj7 (относительный знаковый скачок по 15-мин:
          (RV⁺ − RV⁻) / RV);
  оборот: qv7 (средний дневной оборот перпа $), age, abto (лог оборота 7 сут к обороту d−35…d−8), sabto (стандарт.
          аномальный оборот, Garfinkel и др.), amihud28, tsize7 (средняя сделка $), ntr (лог числа сделок 7 сут к норме);
  поток:  tbi7 = Σ(2·tb − qv)/Σqv за 7 сут (агрессивные покупки перпа);
  фандинг: f7, f28 (сумма ставок), df (f7 − f за d−28…d−8 / 3), fneg7 (доля суток со ставкой < 0), fint (мин. интервал);
  спот:   sshare7 (доля спота Binance в обороте спот + перп), prem7 (средняя премия перпа к споту по закрытиям суток),
          bmom28 (r28 перпа − r28 спота: «базис-моментум» Boons–Prado для перпа);
  Корея:  kshare7 (Upbit + Bithumb к воне / (Корея + перп + спот Binance)), kabn (kshare7 − медиана суточных долей
          d−63 … d−8), kprem7 (премия цены в Корее к перпу);
  CMC:    mcap, lmcap, rank, turn7 ((перп + спот)/капитализация), по снимку CMC топ-200 за сутки до среза (s136).
Доходы после среза не считаются."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402

DAY = C.DAY


def wide(P, col):
    return P.pivot(index="d", columns="s", values=col).sort_index()


def main(per):
    P = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
    days = np.arange(P.d.min(), P.d.max() + DAY, DAY)
    W = {}
    for col in ("c", "h", "l", "qv", "tb", "n", "rv", "rvp", "fsum", "fint", "sqv", "sc", "krv", "krc_upbit", "krc_bithumb"):
        if col in P.columns:
            W[col] = wide(P, col).reindex(days)
    syms = W["c"].columns
    mult = pd.Series({s: C.mult(s) for s in syms})
    c = W["c"].ffill(limit=3)
    qv = W["qv"].fillna(0.0)
    live = W["qv"].notna() & (W["qv"] > 0)
    first = live.idxmax().where(live.any())                       # первые сутки с оборотом
    age = pd.DataFrame(np.subtract.outer(days, first.values.astype(float)) / DAY, index=days, columns=syms)
    lr = np.log(c).diff()
    lr = lr.where(live & live.shift(1, fill_value=False))
    lr = lr.clip(-1.5, 1.5)
    qv7 = qv.rolling(7, min_periods=7).mean()
    liq = (qv7.shift(1) >= 5e6) & (age >= 30)
    alts = [s for s in syms if s not in ("BTC", "ETH")]
    m = lr[alts].where(liq[alts]).mean(axis=1)                    # индекс альтов, равные веса
    F = {}
    F["qv7"] = qv7
    F["age"] = age
    for k in (1, 7, 14, 28, 90):
        F[f"r{k}"] = np.log(c / c.shift(k))
    F["r28s"] = np.log(c.shift(7) / c.shift(28))
    F["dhi90"] = np.log(c / c.rolling(90, min_periods=60).max())
    tp = (W["h"] + W["l"] + W["c"]) / 3
    vw = (tp * qv).rolling(60, min_periods=45).sum() / qv.rolling(60, min_periods=45).sum()
    F["cgo60"] = np.log(c / vw)
    F["lprice"] = np.log(c.div(mult, axis=1))
    F["vol28"] = lr.rolling(28, min_periods=20).std()
    F["rvol7"] = np.sqrt(W["rv"].rolling(7, min_periods=5).sum() / 7)
    mm = pd.DataFrame(np.repeat(m.values[:, None], len(syms), 1), index=days, columns=syms).where(lr.notna())
    R = lr

    def rmean(x, n=28, mp=20):
        return x.rolling(n, min_periods=mp).mean()
    cov = rmean(R * mm) - rmean(R) * rmean(mm)
    vm = rmean(mm * mm) - rmean(mm) ** 2
    F["beta28"] = cov / vm
    vr = rmean(R * R) - rmean(R) ** 2
    F["ivol28"] = np.sqrt((vr - cov ** 2 / vm).clip(lower=0))
    I = (mm < 0).astype(float).where(mm.notna())
    sI = I.rolling(28, min_periods=20).sum()
    dcov = (R * mm * I).rolling(28, min_periods=20).sum() / sI - ((R * I).rolling(28, min_periods=20).sum() / sI) * \
        ((mm * I).rolling(28, min_periods=20).sum() / sI)
    dvm = (mm * mm * I).rolling(28, min_periods=20).sum() / sI - ((mm * I).rolling(28, min_periods=20).sum() / sI) ** 2
    F["dbeta28"] = (dcov / dvm).where(sI >= 8)
    F["skew28"] = lr.rolling(28, min_periods=20).skew()
    sr = c / c.shift(1) - 1
    F["max7"] = sr.rolling(7, min_periods=5).max()
    F["max28"] = sr.rolling(28, min_periods=20).max()
    rvs = W["rv"].rolling(7, min_periods=5).sum()
    rvp = W["rvp"].rolling(7, min_periods=5).sum()
    F["rsj7"] = (2 * rvp - rvs) / rvs
    ref = qv.shift(7).rolling(28, min_periods=20)
    F["abto"] = np.log(qv7 / ref.mean())
    F["sabto"] = (qv7 - ref.mean()) / ref.std()
    F["amihud28"] = (lr.abs() / qv.where(qv > 0)).rolling(28, min_periods=20).mean() * 1e6
    n7 = W["n"].fillna(0).rolling(7, min_periods=7).sum()
    F["tsize7"] = qv.rolling(7, min_periods=7).sum() / n7.where(n7 > 0)
    F["ntr"] = np.log(n7 / 7 / W["n"].fillna(0).shift(7).rolling(28, min_periods=20).mean())
    tb7 = W["tb"].fillna(0).rolling(7, min_periods=7).sum()
    F["tbi7"] = (2 * tb7 - qv.rolling(7, min_periods=7).sum()) / qv.rolling(7, min_periods=7).sum()
    fs = W["fsum"]
    F["f7"] = fs.rolling(7, min_periods=5).sum()
    F["f28"] = fs.rolling(28, min_periods=20).sum()
    F["df"] = F["f7"] - fs.shift(7).rolling(21, min_periods=15).sum() / 3
    F["fneg7"] = (fs < 0).astype(float).where(fs.notna()).rolling(7, min_periods=5).mean()
    F["fint"] = W["fint"].rolling(7, min_periods=1).min()
    if "sqv" in W:
        sq = W["sqv"]
        sq7 = sq.fillna(0).rolling(7, min_periods=7).sum()
        has = sq.notna().rolling(7, min_periods=1).sum() >= 5
        F["sshare7"] = (sq7 / (sq7 + qv.rolling(7, min_periods=7).sum())).where(has)
        pr = c.div(mult, axis=1) / W["sc"] - 1
        F["prem7"] = pr.where(pr.abs() < 0.5).rolling(7, min_periods=5).mean()
        sc = W["sc"].ffill(limit=3)
        F["bmom28"] = F["r28"] - np.log(sc / sc.shift(28))
    else:
        sq7 = None
    if "krv" in W:
        kv = W["krv"]
        kv7 = kv.fillna(0).rolling(7, min_periods=7).sum()
        hask = kv.notna().rolling(7, min_periods=1).sum() >= 5
        den = kv7 + qv.rolling(7, min_periods=7).sum() + (sq7.fillna(0) if sq7 is not None else 0)
        F["kshare7"] = (kv7 / den).where(hask)
        dsh = kv.fillna(0) / (kv.fillna(0) + qv + (W["sqv"].fillna(0) if "sqv" in W else 0))
        dsh = dsh.where(kv.notna())
        F["kabn"] = F["kshare7"] - dsh.shift(7).rolling(56, min_periods=28).median()
        kc = W.get("krc_upbit")
        if kc is None:
            kc = W["krc_bithumb"]
        elif "krc_bithumb" in W:
            kc = kc.fillna(W["krc_bithumb"])
        kp = kc / c.div(mult, axis=1) - 1
        F["kprem7"] = kp.where(kp.abs() < 1).rolling(7, min_periods=3).mean()
        # аномальный оборот на площадке без шорта (Корея): как abto/sabto, но по обороту к воне
        kvf = kv.fillna(0)
        kv7m = kvf.rolling(7, min_periods=7).mean().where(hask)
        kref = kvf.shift(7).rolling(28, min_periods=20)
        F["kv7"] = kv7m
        F["kabto"] = np.log(kv7m / kref.mean().where(kref.mean() > 0))
        F["ksabto"] = (kv7m - kref.mean()) / kref.std().where(kref.std() > 0)
    # срез: понедельник d0 → последняя полная строка — сутки d0 − 1
    mon = C.mondays(per)
    rows = []
    idx = pd.Index(days)
    for d0 in mon:
        dl = d0 - DAY
        if dl not in idx:
            continue
        rec = pd.DataFrame({k: v.loc[dl] for k, v in F.items()})
        rec["liq5"] = (qv7.loc[dl] >= 5e6) & (age.loc[dl] >= 30)
        rec["d0"] = d0
        rows.append(rec.reset_index().rename(columns={"index": "s"}))
    X = pd.concat(rows, ignore_index=True)
    X = X[(X.age >= 30) & (X.qv7 > 0)]
    # CMC топ-200: снимок суток до среза; совпадение тикера и цены 0,8–1,25
    snaps = C.cmc_snapshots()
    mc = []
    for d0, g in X.groupby("d0"):
        S = snaps.get(int(d0 - DAY))
        if S is None:
            continue
        S = S.dropna(subset=["price", "mcap"])
        bym = {}
        for r in S.itertuples():
            bym.setdefault(r.sym, []).append(r)
        for s in g.s:
            b = C.base(s)
            px = float(c.loc[d0 - DAY, s]) / C.mult(s)
            best = None
            for r in bym.get(b, []):
                q = px / r.price if r.price else np.nan
                if 0.8 <= q <= 1.25 and (best is None or r.mcap > best.mcap):
                    best = r
            if best is not None:
                mc.append((d0, s, best.mcap, best.rank, best.circ))
    M = pd.DataFrame(mc, columns=["d0", "s", "mcap", "rank", "circ"])
    X = X.merge(M, on=["d0", "s"], how="left")
    X["lmcap"] = np.log(X.mcap)
    tot7 = X.qv7 * 7 + (X.sshare7 / (1 - X.sshare7) * X.qv7 * 7).fillna(0)
    X["turn7"] = tot7 / 7 / X.mcap
    X["per"] = per
    X.to_pickle(f"{C.OUT}/feat_{per}.pkl")
    L = X[X.liq5.astype(bool) & ~X.s.isin(["BTC", "ETH"])]
    print(per, "срезов", X.d0.nunique(), "строк", len(X), "| ликвидных альтов на срез: медиана", int(L.groupby("d0").size().median()),
          flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
