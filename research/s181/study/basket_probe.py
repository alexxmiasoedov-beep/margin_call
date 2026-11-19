"""s181 — хватит ли монет для недельной корзины «казна в режиме продажи»: по понедельникам — число монет с живым перпом,
у которых за прошлые 28 сут (а) собственные токены казначейства DefiLlama снизились на ≥ 0,5% / ≥ 1% обращения,
(б) выход собственного токена из казны в сети Ethereum (treasury_out.pkl, без перекладки между казнами и сжигания,
без Bancor) ≥ 0,5% / ≥ 1% обращения. Медиана и доля недель с ≥ 5 монетами по периодам. Плюс разбиение событий 🔑⁺
(любой разлок ≥ 1% вне казны, один на перп за 7 сут) по одновременному разлоку доли казны/фонда ≥ 0,5% в ±3 сут.
Только частоты."""
import os
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_events as TE  # noqa: E402
import treasury_outflows as T  # noqa: E402
import treasury_unlocks as TU  # noqa: E402

warnings.filterwarnings("ignore")
DAY = 86400


def mondays():
    return pd.date_range("2020-10-05", "2026-10-26", freq="7D", tz="UTC")


def main():
    P = C.perps()
    # (а) DefiLlama
    S, _ = TE.series()
    W = mondays()
    da = {thr: {w: 0 for w in W} for thr in (0.005, 0.01)}
    have = {w: 0 for w in W}
    for s in S:
        df = TE.daily(s)
        cf = TE.circ_frame(s["cmc"]) if s["cmc"] else None
        if cf is None:
            continue
        df = df.join(cf[["circ"]], how="left")
        df["circ"] = df["circ"].where(df["circ"] > 0).ffill(limit=7)
        for w in W:
            d = int(w.timestamp()) // DAY
            if d not in df.index or (d - 28) not in df.index or not C.alive(s["spans"], d * DAY):
                continue
            h1, h0, c = df.h.get(d), df.h.get(d - 28), df.circ.get(d)
            if np.isnan(h1) or np.isnan(h0) or not c or np.isnan(c):
                continue
            have[w] += 1
            for thr in da:
                if h0 - h1 >= thr * c:
                    da[thr][w] += 1
    # (б) ончейн
    X = pd.read_pickle(f"{C.OUT}/treasury_out.pkl")
    X = X[~X.protos.map(lambda s: "bancor" in s) & ~X.dst.isin(["та же казна/другая казна", "сжигание"])]
    X = X[X.frac.notna()]
    db = {thr: {w: 0 for w in W} for thr in (0.005, 0.01)}
    for perp, y in X.groupby("perp"):
        if perp not in P:
            continue
        for w in W:
            t1 = w.timestamp()
            if not C.alive(P[perp], t1):
                continue
            f = y[(y.t >= t1 - 28 * DAY) & (y.t < t1)].frac.sum()
            for thr in db:
                if f >= thr:
                    db[thr][w] += 1
    print("Недельная корзина: монет на понедельник (медиана; доля недель с ≥ 5 монетами; сделок в месяц при потолке 5) "
          "по периодам")
    for lab, dd in (("DefiLlama, снижение запаса за 28 сут", da), ("Ethereum, выход из казны за 28 сут", db)):
        for thr, m in dd.items():
            out = []
            for p, (a, b) in C.PER.items():
                v = [m[w] for w in W if pd.Timestamp(a, tz="UTC") <= w < pd.Timestamp(b, tz="UTC")]
                out.append(f"{np.median(v):4.1f} ({np.mean(np.array(v) >= 5):4.0%}; сделок {np.mean(np.minimum(v, 5)) * 4.35:4.1f})")
            print(f"  {lab:40s} ≥ {thr:.1%}: " + " / ".join(out))
    out = []
    for p, (a, b) in C.PER.items():
        v = [have[w] for w in W if pd.Timestamp(a, tz="UTC") <= w < pd.Timestamp(b, tz="UTC")]
        out.append(f"{np.median(v):4.1f}")
    print("  монет с рядом DefiLlama (медиана по неделям): " + " / ".join(out))
    # 🔑⁺ с разлоком доли казны
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "s139"))
    import unlock_test as U  # noqa: E402
    K = U.events()
    K["day"] = K["T"] // DAY
    K = K.groupby(["key", "day"]).agg(t=("T", "min"), share=("share", "sum")).reset_index()
    K = K[(K.share >= 0.01) & K.key.isin(P.keys())]
    K = K[[C.alive(P[k], t) for k, t in zip(K.key, K.t)]].rename(columns={"key": "perp"})
    K = T.one_per(K, "perp", 7 * DAY)
    N = TU.events({"noncirculating"})
    N["day"] = N.t // DAY
    for thr in (0.005, 0.01):
        n = N[N.share >= thr]
        co = np.array([bool(len(n[(n.perp == p) & (n.day >= d - 3) & (n.day <= d + 3)])) for p, d in zip(K.perp, K.day)])
        print(f"\n🔑⁺ (разлок ≥ 1% вне казны, 1 на перп за 7 сут): " + " / ".join(f"{C.month_counts(K.t, p):5.2f}" for p in C.PER))
        print(f"  с одновременным разлоком казны/фонда ≥ {thr:.1%} в ±3 сут: " +
              " / ".join(f"{C.month_counts(K.t[co], p):5.2f}" for p in C.PER) + f"  (доля {co.mean():.0%}); без: " +
              " / ".join(f"{C.month_counts(K.t[~co], p):5.2f}" for p in C.PER))


if __name__ == "__main__":
    main()
