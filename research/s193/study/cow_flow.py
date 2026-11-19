"""s193 — эталон «известная продажа частями в сети» (TWAP CoW, `cow_fills.py`) против ленты Binance: виден ли поток.

Для каждого исполнения части (время блока τ) — чистые продажи тейкеров Binance (продажи − покупки, $) на фьючерсе и споте
в окнах [τ−300, τ−60), [τ−60, τ), [τ, τ+12), [τ+12, τ+60), [τ+60, τ+300) с; плацебо — 20 случайных моментов в ±2 ч от τ
не ближе 5 мин к исполнениям этого ордера. Избыток = окно у τ − среднее плацебо; нормировка — на сумму части ($).
Плюс: видят ли детекторы D1/D1n эпизод продаж, пересекающийся с окном ордера, и чем он похож на расписание CoW.
Записано до загрузки лент. Цены после исполнений не считаются — только потоки."""
import os
import sys
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as RUN  # noqa: E402
import tape  # noqa: E402

D = "/home/user/mc_data/s193"
TMP = f"{D}/tmp_cow"
WIN = [(-300, -60), (-60, 0), (0, 12), (12, 60), (60, 300)]


def flows(O, taus):
    """Чистые продажи тейкеров ($) в окнах относительно моментов taus (сек)."""
    t = O["t"] / 1000.0
    sv = np.where(O["s"] < 0, O["v"], 0.0)
    bv = np.where(O["s"] > 0, O["v"], 0.0)
    cs = np.r_[0.0, np.cumsum(sv)]
    cb = np.r_[0.0, np.cumsum(bv)]
    out = np.zeros((len(taus), len(WIN)))
    for k, (a, b) in enumerate(WIN):
        i0 = np.searchsorted(t, taus + a, "left")
        i1 = np.searchsorted(t, taus + b, "left")
        out[:, k] = (cs[i1] - cs[i0]) - (cb[i1] - cb[i0])
    return out


def main():
    os.makedirs(TMP, exist_ok=True)
    F = pd.read_pickle(f"{D}/cow_fills.pkl")
    rng = np.random.default_rng(193)
    rows, det_rows = [], []
    cache = {}
    for o in F:
        fl = [(b, ts, a) for b, ts, a in o["fills"] if ts]
        if len(fl) < 3:
            continue
        taus = np.array(sorted(ts for _, ts, _ in fl), float)
        amt = np.array([a for _, ts, a in sorted(fl, key=lambda z: z[1])], float)
        usd = amt * o["price"]
        days = sorted(set((taus // 86400 * 86400).astype(int)))
        for mkt in ("um", "spot"):
            for d in days:
                key = (mkt, o["sym"], d)
                if key not in cache:
                    path = f"{TMP}/{mkt}_{o['sym']}_{d}.zip"
                    code = RUN.fetch(RUN.url(mkt, o["sym"], d), path)
                    if code != 200:
                        cache[key] = None
                        continue
                    try:
                        df = tape.read_zip(path)
                        df = df[(df["T"] >= d * 1000) & (df["T"] < (d + 86400) * 1000)]
                        O, p, t, side, q = tape.orders(df)
                        ctx = tape.Ctx(O)
                        rq, _ = tape.d1_exact(O, ctx, d * 1000)
                        rn, _ = tape.d1_notional(O, ctx, d * 1000)
                        cache[key] = (O, [r for r in rq + rn if np.isfinite(r["det_t"])])
                    except Exception as e:  # noqa: BLE001
                        print("ошибка", key, e)
                        cache[key] = None
                    finally:
                        os.remove(path) if os.path.exists(path) else None
                v = cache[key]
                if v is None:
                    continue
                O, eps = v
                m = (taus >= d) & (taus < d + 86400 - 300) & (taus >= d + 300)
                if not m.any():
                    continue
                f_ev = flows(O, taus[m])
                # плацебо
                pl = []
                for tau in taus[m]:
                    c = rng.uniform(tau - 7200, tau + 7200, 200)
                    c = c[(c > d + 300) & (c < d + 86400 - 300)]
                    c = c[np.min(np.abs(c[:, None] - taus[None, :]), axis=1) > 300][:20]
                    pl.append(flows(O, c).mean(axis=0) if len(c) else np.full(len(WIN), np.nan))
                pl = np.array(pl)
                for i, (fe, fp, u) in enumerate(zip(f_ev, pl, usd[m])):
                    rows.append(dict(mkt=mkt, sym=o["sym"], owner=o["owner"], sec=o["sec"], n=o["n"], part_usd=u,
                                     tau=taus[m][i], **{f"ev{k}": fe[k] for k in range(len(WIN))},
                                     **{f"pl{k}": fp[k] for k in range(len(WIN))}))
                # детекторы: эпизод продаж, пересекающийся с окном ордера
                w0, w1 = taus.min() * 1000, taus.max() * 1000 + o["sec"] * 1000
                for e in eps:
                    if e["side"] < 0 and e["t0"] < w1 and e["t1"] > w0:
                        det_rows.append(dict(mkt=mkt, sym=o["sym"], owner=o["owner"], sec=o["sec"], med=e["med"],
                                             vchild=e["vchild"], n=e["n"], dur=e["dur"], sh=e["sh_side"],
                                             part_usd=float(np.median(usd))))
        print(o["sym"], o["n"], o["sec"], f"{o['tot_usd']:,.0f} $", "исполнений", len(fl), flush=True)
    R = pd.DataFrame(rows)
    pd.to_pickle(dict(flows=R, det=pd.DataFrame(det_rows)), f"{D}/cow_flow.pkl")
    if not len(R):
        print("нет данных")
        return
    print(f"\nисполнений с лентой: {len(R)} (ордеров {R.owner.nunique()}), фьючерсы {int((R.mkt == 'um').sum())}, "
          f"спот {int((R.mkt == 'spot').sum())}")
    for mkt in ("um", "spot"):
        x = R[R.mkt == mkt]
        if not len(x):
            continue
        print(f"\n== {mkt}: избыток чистых продаж тейкеров Binance относительно плацебо, доля суммы части ==")
        for k, (a, b) in enumerate(WIN):
            ex = (x[f"ev{k}"] - x[f"pl{k}"]) / x.part_usd
            g = pd.DataFrame(dict(o=x.owner, e=ex)).groupby("o").e.mean()        # кластер — ордер
            t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g))) if len(g) > 2 else np.nan
            print(f"  [{a:+4d}, {b:+4d}) с: среднее по исполнениям {ex.mean():+.3f}, медиана {ex.median():+.3f}; по ордерам "
                  f"{g.mean():+.3f} (t {t:.2f}, ордеров {len(g)})")
    Dd = pd.DataFrame(det_rows)
    if len(Dd):
        print(f"\nэпизоды продаж D1/D1n, пересекающиеся с окнами ордеров: {len(Dd)} у {Dd.owner.nunique()} ордеров; "
              f"шаг эпизода к шагу CoW (медиана) {np.median(Dd.med / Dd.sec):.3f}; часть эпизода к части CoW "
              f"(медиана) {np.median(Dd.vchild / Dd.part_usd):.4f}")


if __name__ == "__main__":
    main()
