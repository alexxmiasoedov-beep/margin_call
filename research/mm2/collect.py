"""Новые данные для моментов памп/дамп/покой → mm2/raw/<монета>.pkl:
стакан фьючерса (bookDepth, последний снимок каждой минуты, ±0,2…±5%), спот и фьючерс по 1 мин (объём, сделки, покупки тейкеров)."""
import pickle, datetime, random, re, os, io, zipfile, sys
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor
import bv
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def book_1m(sym, d):
    data = bv.fetch(f"daily/bookDepth/{sym}USDT/{sym}USDT-bookDepth-{d}.zip")
    if not data: return None
    try:
        z = zipfile.ZipFile(io.BytesIO(data)); df = pd.read_csv(z.open(z.namelist()[0]))
    except Exception: return None
    df["t"] = pd.to_datetime(df.timestamp).values.astype("datetime64[s]").astype("int64") // 60 * 60
    p = df.pivot_table(index="t", columns="percentage", values="notional", aggfunc="last")
    p = p.reindex(columns=[-5.0, -4.0, -3.0, -2.0, -1.0, -0.2, 0.2, 1.0, 2.0, 3.0, 4.0, 5.0])
    return p.index.values.astype(np.int64), p.values.astype(np.float32)
def load_coin(arg):
    s, days = arg
    fn = f"{os.environ.get('RAWDIR', 'mm2/raw')}/{s}.pkl"
    if os.path.exists(fn): return s, "кэш"
    out = {"book": None, "spot": None, "fut": None, "spot_sym": None}
    bt, bm = [], []
    for d in days:
        b = book_1m(s, d)
        if b is not None: bt.append(b[0]); bm.append(b[1])
    if bt: out["book"] = (np.concatenate(bt), np.vstack(bm))
    try: out["fut"] = bv.kfull(s, "klines", "1m", (), days)
    except Exception: pass
    for name in dict.fromkeys([re.sub(r"^(1000000|100000|10000|1000)", "", s), s]):
        try: a = bv.kfull_spot(name, days)
        except Exception: a = None
        if a is not None: out["spot"], out["spot_sym"] = a, name; break
    pickle.dump(out, open(fn + ".tmp", "wb")); os.replace(fn + ".tmp", fn)
    return s, "ok"
if __name__ == "__main__":
    random.seed(5)
    K = pickle.load(open("kaia/k15_all.pkl", "rb")); E = pickle.load(open("mm2/events.pkl", "rb"))
    ev_coins = {s for g in ("памп", "дамп") for s, _ in E[g]}
    calm = [x for x in E["покой"] if x[0] in ev_coins] + random.sample([x for x in E["покой"] if x[0] not in ev_coins], 600)
    M = [("памп", s, i) for s, i in E["памп"]] + [("дамп", s, i) for s, i in E["дамп"]] + [("покой", s, i) for s, i in calm]
    pickle.dump(M, open("mm2/moments.pkl", "wb"))
    need = {}
    for g, s, i in M:
        t0 = K[s][i, 0] + 900
        need.setdefault(s, set()).update({day(t0 - 86400), day(t0 - 1)})
    print("моментов", len(M), "| монет", len(need), "| монето-дней", sum(len(v) for v in need.values()), flush=True)
    jobs = [(s, sorted(v)) for s, v in sorted(need.items())]
    with ProcessPoolExecutor(4) as ex:
        for n, (s, st) in enumerate(ex.map(load_coin, jobs, chunksize=2)):
            if n % 50 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), "монет", n, s, st, flush=True)
    print("готово", flush=True)
