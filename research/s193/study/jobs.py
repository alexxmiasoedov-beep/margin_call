"""s193 — список заданий «монета × сутки × рынок» для потоковой обработки лент aggTrades (data.binance.vision).

Выборка (seed 193, записана до загрузки лент):
- SRS: на каждые k-е сутки периода (2020–2022 и 2022–2024 — каждые 8 сут, 2024–2026 — каждые 5 сут; шаг сдвигает день
  недели) — 45 случайных монет из ликвидной вселенной этих суток (как s183: перп-альт без BTC, ETH, акций, металлов,
  стейблкоинов; средний оборот перпа за 7 сут до суток ≥ 5 млн $; первая свеча с оборотом ≥ 30 сут назад). Рынок —
  фьючерсы USDT-M. У 10% заданий SRS — синтетические TWAP-вставки (эталон полноты детектора).
- 🔑⁺ (s142): сутки разлока T и следующие (фьючерсы); в 2024–2026 гг. — 400 случайных событий из 836.
- 🐋 (s167lv, правило бота B, |r24| ≤ 5%): до 250 событий на период — сутки завода t и контроль t − 7 сут, фьючерсы и спот.
Только список заданий: цены и доходы не читаются."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data"
OUT = f"{D}/s193"
DAY = 86400
STEP = {"2020–2022": 8, "2022–2024": 8, "2024–2026": 5}
NPER = 45


def universe():
    """{период: (DataFrame s, d, qv, qv7, age, n)}; возраст — от первой суточной свечи с оборотом во всех трёх файлах."""
    bad = C.bad_set() | {"BTC", "ETH"}
    P = {per: pd.read_pickle(f"{D}/s183/daily_{per}.pkl")[["s", "d", "qv", "n"]] for per in C.PERS}
    allx = pd.concat(P.values())
    first = allx[allx.qv > 0].groupby("s").d.min()
    out = {}
    for per, x in P.items():
        x = x[~x.s.isin(bad)].sort_values(["s", "d"]).copy()
        x["qv7"] = x.groupby("s").qv.transform(lambda v: v.shift(1).rolling(7, min_periods=5).mean())
        x["age"] = (x.d - x.s.map(first)) / DAY
        out[per] = x
    return out


def main():
    rng = np.random.default_rng(193)
    U = universe()
    jobs = {}

    def add(mkt, s, d, tag, per, inj=0):
        k = (mkt, s, int(d))
        if k not in jobs:
            jobs[k] = dict(mkt=mkt, s=s, d=int(d), per=per, tags=set(), inj=0)
        jobs[k]["tags"].add(tag)
        jobs[k]["inj"] = max(jobs[k]["inj"], inj)

    stat = {}
    for per in C.PERS:
        x = U[per]
        uni = x[(x.qv7 >= 5e6) & (x.age >= 30)]
        days = np.array(sorted(uni.d.unique()))
        days = days[::STEP[per]]
        nsrs = 0
        usize = []
        for d in days:
            cand = uni[uni.d == d].s.values
            usize.append(len(cand))
            pick = rng.choice(cand, size=min(NPER, len(cand)), replace=False)
            for s in pick:
                add("um", s, d, "srs", per, inj=int(rng.random() < 0.10))
                nsrs += 1
        stat[per] = dict(days=len(days), srs=nsrs, usize=float(np.median(usize)))
        perps = set(x.s.unique())

        def perp_of(s):
            s = s[:-4] if s.endswith("USDT") else s
            if s in perps:
                return s
            for m in ("1000", "1000000", "1M", "100", "10000"):
                if m + s in perps:
                    return m + s
            return None
        # 🔑⁺ — сутки разлока и следующие
        u = pd.read_pickle(f"{D}/s142_{per}.pkl")[["s", "T"]]
        if per == "2024–2026" and len(u) > 400:
            u = u.iloc[np.sort(rng.choice(len(u), 400, replace=False))]
        nu = 0
        for s, T in zip(u.s, u["T"]):
            p = perp_of(s)
            if p is None:
                continue
            d0 = (int(T) // DAY) * DAY
            for d in (d0, d0 + DAY):
                add("um", p, d, "unlock", per)
            nu += 1
        # 🐋 — сутки завода (вход журнала t) и контроль t − 7 сут; фьючерсы и спот
        w = pd.read_pickle(f"{D}/s167lv_{per}.pkl")[["s", "t", "B", "r24"]]
        w = w[w.B.astype(bool) & (w.r24.abs() <= 0.05)]
        if len(w) > 250:
            w = w.iloc[np.sort(rng.choice(len(w), 250, replace=False))]
        nw = 0
        for s, t in zip(w.s, w.t):
            p = perp_of(s)
            if p is None:
                continue
            d0 = (int(t) // DAY) * DAY
            for mkt in ("um", "spot"):
                add(mkt, p, d0, "whale", per)
                add(mkt, p, d0 - 7 * DAY, "whale_ctl", per)
            nw += 1
        stat[per].update(unlock_events=nu, whale_events=nw)
    J = pd.DataFrame(jobs.values())
    J["tags"] = J.tags.map(lambda z: ",".join(sorted(z)))
    J = J.sort_values(["per", "d", "mkt", "s"]).reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    J.to_pickle(f"{OUT}/jobs.pkl")
    for per, v in stat.items():
        print(per, v)
    print("заданий:", len(J), J.groupby(["per", "mkt"]).size().to_dict())
    print("с синтетическими вставками:", int(J.inj.sum()))
    for per in C.PERS:
        y = U[per]
        m = J[J.per == per].merge(y[["s", "d", "n"]], on=["s", "d"], how="left")
        print(per, "сделок (перп) в выбранных сутках, млн:", round(m.n.sum() / 1e6, 1),
              "медиана на сутки, тыс.:", round(m.n.median() / 1e3, 1))


if __name__ == "__main__":
    main()
