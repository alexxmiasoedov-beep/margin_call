"""s179 — «неоплаченная премия» на упорах фандинга в пол в 2020–2022 и 2022–2024 гг. (премия из архива Binance)
и число монето-суток с глубокой отрицательной ставкой по трём периодам. Без доходов и цен после событий.

Запуск: python3 -I probe_unpaid_old.py <папка данных>
Премия: data.binance.vision futures/um monthly premiumIndexKlines 1h (закрытие часа), кэш — <данные>/s179/cache/.
F* = [P̄ + clamp(0,01% − P̄, ±0,05%)] / (8/N), P̄ — среднее часовых закрытий интервала с линейными весами 1…n.
"""
import io
import os
import pickle
import sys
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("pfc", os.path.join(HERE, "probe_funding_caps.py"))
pfc = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], D]
spec.loader.exec_module(pfc)
CACHE = os.path.join(D, "s179/cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "research-script/1.0"}


def fetch(sym, month):
    fn = os.path.join(CACHE, f"prem_{sym}_{month}.csv")
    if os.path.exists(fn):
        return open(fn).read()
    url = (f"https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/{sym}USDT/1h/"
           f"{sym}USDT-1h-{month}.zip")
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            txt = z.read(z.namelist()[0]).decode()
            open(fn, "w").write(txt)
            return txt
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(fn, "w").write("")
                return ""
            time.sleep(3 + 5 * i)
        except Exception:
            time.sleep(3 + 5 * i)
    return None


def prem_series(sym, months):
    rows = []
    for m in months:
        txt = fetch(sym, m)
        if not txt:
            continue
        for ln in txt.splitlines():
            p = ln.split(",")
            if p and p[0][:1].isdigit():
                rows.append((int(p[0]) // 1000, float(p[4])))
    if not rows:
        return None
    a = np.array(sorted(set(rows)))
    return a[:, 0].astype(np.int64), a[:, 1]


def main():
    for name, path, a, b in pfc.PERIODS:
        t0, t1 = pfc.ts(a), pfc.ts(b)
        F = pickle.load(open(os.path.join(D, path), "rb"))
        syms = [s for s in F if s not in pfc.BAD and not s.endswith("USDC") and len(F[s])]
        cd05, cd1, cd2 = set(), set(), set()
        floors = []
        for s in syms:
            x = F[s]
            x = x[(x[:, 0] >= t0) & (x[:, 0] < t1)]
            if not len(x):
                continue
            t, n, r = x[:, 0], x[:, 1], x[:, 2]
            e8 = r * 8.0 / np.where(n > 0, n, 8.0)
            for thr, st in ((-0.005, cd05), (-0.01, cd1), (-0.02, cd2)):
                for tt in t[e8 <= thr]:
                    st.add((s, int(tt // 86400)))
            k = pfc.at_known(r) & (r < 0)
            floors += [(s, float(t[i]), float(n[i]), float(r[i])) for i in np.flatnonzero(k)]
        months_n = (t1 - t0) / 86400 / 30.44
        print(f"== {name}: монето-суток со ставкой в 8-ч эквиваленте ≤ −0,5% — {len(cd05) / months_n:.1f} в месяц, "
              f"≤ −1% — {len(cd1) / months_n:.1f}, ≤ −2% — {len(cd2) / months_n:.1f}")
        if name == "2024–2026":
            continue                      # премия этого периода — в probe_funding_caps.py (s12/prem.pkl)
        res = []
        need = {}
        for s, t, n, r in floors:
            for dt_ in (t - n * 3600, t):
                need.setdefault(s, set()).add(pd.Timestamp(dt_, unit="s").strftime("%Y-%m"))
        P = {s: prem_series(s, sorted(ms)) for s, ms in need.items()}
        for s, t, n, r in floors:
            if P.get(s) is None:
                continue
            pt, pv = P[s]
            sel = (pt >= t - n * 3600) & (pt <= t - 3600)
            if sel.sum() < max(1, int(n * 0.75)):
                continue
            p = pv[sel]
            w = np.arange(1, len(p) + 1, dtype=float)
            pbar = float((w * p).sum() / w.sum())
            fstar = (pbar + np.clip(0.0001 - pbar, -0.0005, 0.0005)) / (8.0 / n)
            res.append((s, t, n, r, fstar))
        if res:
            u = pd.DataFrame(res, columns=["s", "t", "N", "r", "fstar"])
            q = u.fstar / u.r
            print(f"   упоров в пол с премией {len(u)} из {len(floors)}; F*/пол медиана {q.median():.2f}, "
                  f"доля F* ≤ 1,5·пол {np.mean(q >= 1.5):.0%}, ≤ 2·пол {np.mean(q >= 2):.0%}; "
                  f"после 11.05.2021 — {int((u.t >= pfc.ts('2021-05-11 13:00')).sum())} упоров")
        del F


if __name__ == "__main__":
    main()
