"""s294 Г8 — признаки ленты сделок в свече пампа (запись правил — ВЫВОДЫ.md).

Входы — 🛒 (s270, группа S) и 🇰🇷 (s277) трёх периодов, памп обоих журналов — один раз. Для каждого пампа — дневные
архивы aggTrades data.binance.vision перпа USDT-M и спота XXXUSDT за сутки окна [te − 2 ч, te). Архивы читаются
в памяти и не хранятся. Заявка тейкера ≈ подряд идущие aggTrades с одним временем (мс) и одной стороной.
Признаки по площадке (F — перп, S — спот) и окну (A — свеча пампа 15 мин, B — 2 ч):
  V, Vb — оборот и покупки тейкеров, $; n — заявок; для q ∈ {0,90; 0,98; 0,995}: bb_q, bs_q — крупные покупки и
  продажи (сумма заявки ≥ q-квантиля сумм заявок той же площадки в том же окне); sb, ss — мелкие (≤ медианы).
Выход — /home/user/mc_data/s294/g8_feat.jsonl (дописывается, повторный запуск продолжает).
Запуск: python3 -I research/s294/g8_fetch.py"""
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s294/g8_feat.jsonl"
PERS = ("2020–2022", "2022–2024", "2024–2026")
QS = (0.90, 0.98, 0.995)
UA = {"User-Agent": "research-script/1.0"}


def entries():
    rows = []
    for per in PERS:
        a = pd.read_pickle(f"{D}/s270_{per}.pkl")
        a = a[(a.grp == "S") & (a.side == -1) & (a.sl == 0.1) & (a.hold == 8)][["s", "te"]]
        b = pd.read_pickle(f"{D}/s277_{per}.pkl")
        b = b[(b.h == "🇰🇷") & (b.ex == "8 ч")][["s", "te"]]
        u = pd.concat([a, b]).drop_duplicates()
        rows += [(per, str(s), int(te)) for s, te in zip(u.s, u.te)]
    return rows


def fetch(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(3 + 5 * i)
    raise RuntimeError(f"не скачалось: {url}")


def load(kind, sym, days, lo, hi):
    """Сделки площадки за [lo, hi) мс: время, сумма $, продажа тейкера; None — архива нет."""
    base = "futures/um" if kind == "F" else "spot"
    parts = []
    for day in days:
        data = fetch(f"https://data.binance.vision/data/{base}/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip")
        if data is None:
            return None
        z = zipfile.ZipFile(io.BytesIO(data))
        raw = z.read(z.namelist()[0])
        del data, z
        hdr = 0 if not raw[:1].isdigit() else None
        x = pd.read_csv(io.BytesIO(raw), header=hdr, usecols=[1, 2, 5, 6], names=None if hdr == 0 else range(8 if kind == "S" else 7),
                        dtype={1: np.float64, 2: np.float64, 5: np.int64, 6: str} if hdr is None else None, engine="c")
        del raw
        x.columns = ["p", "q", "t", "m"]
        t = x.t.values.astype(np.int64)
        if len(t) and t.max() > 10 ** 14:                     # спот с 2025 г. — микросекунды
            t = t // 1000
        k = (t >= lo) & (t < hi)
        m = x.m[k]
        sell = m.values.astype(bool) if m.dtype == bool else m.astype(str).str.lower().eq("true").values
        parts.append((t[k], (x.p.values[k] * x.q.values[k]), sell))
        del x
    t = np.concatenate([p[0] for p in parts]); v = np.concatenate([p[1] for p in parts]); s = np.concatenate([p[2] for p in parts])
    return t, v, s


def orders(t, v, s):
    if not len(t):
        return t, v, s
    st = np.ones(len(t), bool)
    st[1:] = (t[1:] != t[:-1]) | (s[1:] != s[:-1])
    i = np.flatnonzero(st)
    return t[i], np.add.reduceat(v, i), s[i]


def feats(t, v, s, lo, hi, tag, out):
    k = (t >= lo) & (t < hi)
    ot, ov, os_ = orders(t[k], v[k], s[k])
    out[f"{tag}_V"] = float(ov.sum()); out[f"{tag}_Vb"] = float(ov[~os_].sum()); out[f"{tag}_n"] = int(len(ov))
    if len(ov) < 5:
        return
    for q in QS:
        thr = np.quantile(ov, q); big = ov >= thr
        out[f"{tag}_bb{q}"] = float(ov[big & ~os_].sum()); out[f"{tag}_bs{q}"] = float(ov[big & os_].sum())
    med = np.median(ov); sm = ov <= med
    out[f"{tag}_sb"] = float(ov[sm & ~os_].sum()); out[f"{tag}_ss"] = float(ov[sm & os_].sum())


def one(r):
    per, s, te = r
    days = sorted({pd.Timestamp(te - 7200, unit="s").strftime("%Y-%m-%d"), pd.Timestamp(te - 1, unit="s").strftime("%Y-%m-%d")})
    lo, hi = (te - 7200) * 1000, te * 1000
    out = dict(per=per, s=s, te=te)
    try:
        f = load("F", f"{s}USDT", days, lo, hi)
        if f is None:
            out["err"] = "нет перпа"
            return out
        for w, a in (("A", (te - 900) * 1000), ("B", lo)):
            feats(*f, a, hi, f"F{w}", out)
        del f
        sp = None
        for b in dict.fromkeys((s, re.sub(r"^(1000000|100000|10000|1000)", "", s))):
            sp = load("S", f"{b}USDT", days, lo, hi)
            if sp is not None:
                out["spot"] = b
                break
        if sp is not None:
            for w, a in (("A", (te - 900) * 1000), ("B", lo)):
                feats(*sp, a, hi, f"S{w}", out)
    except Exception as e:
        out["err"] = f"{type(e).__name__}: {e}"[:200]
    return out


def main():
    rows = entries()
    done = set()
    if os.path.exists(OUT):
        for ln in open(OUT):
            d = json.loads(ln)
            if "err" not in d or d["err"] == "нет перпа":
                done.add((d["per"], d["s"], d["te"]))
    todo = [r for r in rows if r not in done]
    print(f"пампов {len(rows)}, готово {len(done)}, осталось {len(todo)}", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(int(os.environ.get("G8_WORKERS", "6"))) as ex, open(OUT, "a") as fo:
        for i, d in enumerate(ex.map(one, todo, chunksize=2)):
            fo.write(json.dumps(d, ensure_ascii=False) + "\n"); fo.flush()
            if i % 100 == 0:
                print(f"  {i}/{len(todo)} {time.time() - t0:.0f} с  {d.get('err', '')}", flush=True)
    print(f"готово за {time.time() - t0:.0f} с", flush=True)


if __name__ == "__main__":
    main()
