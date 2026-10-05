"""Таблица кандидатов для поиска параметров сигнала (вся история канала, 15-мин свечи фьючерсов Binance).
Кандидат = (монета, 15-мин свеча), в которой монета была в посте канала, серия ≥ 1 ч. Решение — на закрытии свечи,
вход по close. Признаки — только прошлое. Исходы: первое касание уровней тейка (цена сделок ниже уровня) и стопа
(максимум свечи ≥ уровня; по цене сделок — строже, чем по марк-цене) на 48 ч вперёд, закрытия через 24/48 ч, фандинг."""
import json, re, io, datetime, pickle, zipfile
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc
ts = lambda *a: int(datetime.datetime(*a, tzinfo=UTC).timestamp())
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
G0, G1 = ts(2025, 1, 1), ts(2026, 10, 1)                 # общая сетка 15-мин свечей
GRID = np.arange(G0, G1, 900); NG = len(GRID)
T0, T1 = ts(2025, 2, 23), ts(2026, 9, 28)
GAP, H = 1800, 192
TPS = [4, 6, 8, 10, 15, 20]; SLS = [10, 15, 20, 25, 30]
num = lambda s: float(s[:-1]) * {"K": 1e3, "M": 1e6, "B": 1e9}[s[-1]] if s[-1] in "KMB" else float(s)

# ---------- посты канала
POSTS = {}
for fn in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl"):
    for ln in open(fn):
        p = json.loads(ln); POSTS[p[0]] = p
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+(-?[\d.]+))?\s*$')
rows = []
for pid, tstr, txt in POSTS.values():
    ep = int(datetime.datetime.fromisoformat(tstr).timestamp())
    ms = [m for m in (rx.match(x.strip()) for x in txt.splitlines()) if m]
    for pos, m in enumerate(ms):
        rows.append((m.group(1), ep, num(m.group(2)), num(m.group(3)), float(m.group(4)), float(m.group(5)) if m.group(5) else np.nan, pos, len(ms)))
P = pd.DataFrame(rows, columns=["sym", "ep", "bor", "rep", "br", "chng", "pos", "ncoins"]).drop_duplicates(["sym", "ep"]).sort_values(["sym", "ep"])
P["gap"] = P.groupby("sym").ep.diff()
P["run_id"] = (P.gap.isna() | (P.gap > GAP)).groupby(P.sym).cumsum()
g = P.groupby(["sym", "run_id"])
P["run_h"] = (P.ep - g.ep.transform("min")) / 3600
P["run_posts"] = g.cumcount() + 1
P["bor_g"] = P.bor / g.bor.transform("first")
P["bar"] = P.ep // 900 * 900
C = P[(P.run_h >= 1) & (P.bar >= T0) & (P.bar < T1)].sort_values("ep").groupby(["sym", "bar"]).tail(1)
print("строк в постах", len(P), "| кандидатов (монета×свеча, серия ≥1ч)", len(C), "| монет", C.sym.nunique(), flush=True)

# ---------- свечи на общей сетке
def load(sym):
    out = []
    for m in MONTHS:
        data = bv.fetch(f"monthly/klines/{sym}USDT/15m/{sym}USDT-15m-{m}.zip")
        if not data: continue
        try:
            df = pd.read_csv(io.BytesIO(data), compression="zip", header=None, usecols=[0, 1, 2, 3, 4, 7, 10])
        except Exception:
            continue
        df = df[pd.to_numeric(df[0], errors="coerce").notna()].astype(float)
        out.append(df.values)
    if not out: return sym, None
    a = np.concatenate(out); a[:, 0] = a[:, 0] // 1000
    k = ((a[:, 0] - G0) // 900).astype(np.int64); ok = (k >= 0) & (k < NG)
    arr = np.full((NG, 6), np.nan, np.float32); arr[k[ok]] = a[ok, 1:]
    return sym, arr                                      # o h l c qv tbq
syms = sorted(C.sym.unique()) + ["BTC"]
with ThreadPoolExecutor(8) as ex:
    K = dict(x for x in ex.map(load, syms) if x[1] is not None)
BTC = K.pop("BTC")
print("монет со свечами", len(K), flush=True)
with ThreadPoolExecutor(16) as ex:
    FU = dict(zip(K, ex.map(lambda s: bv.funding(s, MONTHS), K)))

# ---------- рынок: BTC и ширина рынка (доля монет из канала, выросших за сутки; медиана изменения за 7 дней)
cb = pd.Series(BTC[:, 3]).ffill().values
btc = {f"btc_{lab}": cb / np.roll(cb, n) - 1 for lab, n in (("24h", 96), ("7d", 672), ("30d", 2880))}
for v in btc.values(): v[:2880] = np.nan
CM = np.vstack([K[s][:, 3] for s in K])                 # монеты × сетка
ch24 = CM / np.roll(CM, 96, axis=1) - 1; ch24[:, :96] = np.nan
ch7 = CM / np.roll(CM, 672, axis=1) - 1; ch7[:, :672] = np.nan
with np.errstate(invalid="ignore"):
    breadth = np.nanmean(np.where(np.isnan(ch24), np.nan, (ch24 > 0).astype(float)), axis=0)
alt7 = np.nanmedian(ch7, axis=0)
del CM, ch24, ch7

# ---------- признаки и исходы по монетам
from numpy.lib.stride_tricks import sliding_window_view as swv
def roll(x, n, f):
    return getattr(pd.Series(x).rolling(n, min_periods=max(2, n // 2)), f)().values
feats = []; CF = {}
for si, (sym, A) in enumerate(K.items()):
    cs = C[C.sym == sym]
    if not len(cs): continue
    o, h, l, c, qv, tb = [A[:, j].astype(np.float64) for j in range(6)]
    live = ~np.isnan(c)
    cf = pd.Series(c).ffill().values
    h = np.where(np.isnan(h), cf, h); l = np.where(np.isnan(l), cf, l)
    qv = np.nan_to_num(qv); tb = np.nan_to_num(tb)
    i = ((cs.bar.values - G0) // 900).astype(np.int64)
    ok = live[i] & (i >= 96); cs = cs[ok]; i = i[ok]
    if not len(i): continue
    e = c[i]
    F = {"sym": sym, "bar": cs.bar.values, "i": i, "e": e}
    for col in ("run_h", "run_posts", "bor", "rep", "br", "chng", "bor_g", "pos", "ncoins"): F[col] = cs[col].values
    def back(n):
        j = i - n; v = np.full(len(i), np.nan); m = j >= 0; v[m] = e[m] / cf[j[m]] - 1; return v * 100
    for lab, n in (("1h", 4), ("2h", 8), ("4h", 16), ("8h", 32), ("12h", 48), ("24h", 96), ("3d", 288), ("7d", 672)): F[f"ch_{lab}"] = back(n)
    F["rise_before"] = (cf[i - 16] / cf[np.maximum(i - 96, 0)] - 1) * 100
    hm96, lm96, hm16, lm16 = roll(h, 96, "max"), roll(l, 96, "min"), roll(h, 16, "max"), roll(l, 16, "min")
    F["from_high24"] = (e / hm96[i] - 1) * 100; F["from_low24"] = (e / lm96[i] - 1) * 100
    F["from_high4h"] = (e / hm16[i] - 1) * 100; F["from_low4h"] = (e / lm16[i] - 1) * 100
    lr = np.diff(np.log(cf), prepend=np.nan); F["vol24"] = roll(lr, 96, "std")[i] * 100
    q4, q16, q96, t4 = roll(qv, 4, "sum"), roll(qv, 16, "sum"), roll(qv, 96, "sum"), roll(tb, 4, "sum")
    with np.errstate(divide="ignore", invalid="ignore"):
        F["vrel_1h"] = q4[i] / (q96[i] / 24); F["vrel_4h"] = q16[i] / (q96[i] / 6); F["tbuy_1h"] = t4[i] / q4[i]
    F["qv24_m"] = q96[i] / 1e6
    fu = FU.get(sym); te = GRID[i] + 900
    if fu is not None and len(fu) > 1:
        k = np.searchsorted(fu[:, 0], te, "right") - 1; k1 = np.clip(k, 1, len(fu) - 1)
        ih = np.maximum((fu[k1, 0] - fu[k1 - 1, 0]) / 3600, 1)
        F["f_per"] = np.where(k >= 1, fu[k1, 1] * 100, np.nan); F["f_h"] = F["f_per"] / ih; F["f_int"] = np.where(k >= 1, ih, np.nan)
        csum = np.concatenate([[0], np.cumsum(fu[:, 1])])
        F["f_24h"] = (csum[np.searchsorted(fu[:, 0], te, "right")] - csum[np.searchsorted(fu[:, 0], te - 86400, "right")]) * 100
        cfg = csum[np.searchsorted(fu[:, 0], GRID + 900, "right")]           # накопленный фандинг на конец каждой свечи
    else:
        for col in ("f_per", "f_h", "f_int", "f_24h"): F[col] = np.full(len(i), np.nan)
        cfg = np.zeros(NG)
    CF[sym] = np.concatenate([cfg, np.full(H + 2, cfg[-1])]).astype(np.float64)
    for col, v in btc.items(): F[col] = v[i] * 100
    F["breadth"] = breadth[i]; F["alt7"] = alt7[i] * 100
    dt = pd.to_datetime(te, unit="s"); F["hour"] = dt.hour.values; F["wday"] = dt.weekday.values
    # исходы
    hp = np.concatenate([h, np.full(H + 1, np.nan)]); lp = np.concatenate([l, np.full(H + 1, np.nan)])
    cp = np.concatenate([np.where(live, c, np.nan), np.full(H + 1, np.nan)])
    HW, LW, CW = swv(hp, H)[i + 1], swv(lp, H)[i + 1], swv(cp, H)[i + 1]
    avail = np.minimum(H, NG - 1 - i)
    for tp in TPS:
        hit = LW < (e * (1 - tp / 100))[:, None]; F[f"jtp{tp}"] = np.where(hit.any(1), hit.argmax(1) + 1, 255).astype(np.uint8)
    for sl in SLS:
        hit = HW >= (e * (1 + sl / 100))[:, None]; F[f"jsl{sl}"] = np.where(hit.any(1), hit.argmax(1) + 1, 255).astype(np.uint8)
    lastv = np.where(~np.isnan(CW), np.arange(H)[None, :], -1).max(1)          # последний бар с данными (делистинг)
    F["avail"] = np.minimum(avail, lastv + 1).astype(np.int16)
    F["r24"] = CW[:, 95] / e; F["r48"] = CW[:, 191] / e
    F["rlast"] = CW[np.arange(len(i)), np.maximum(F["avail"] - 1, 0)] / e
    feats.append(pd.DataFrame(F))
    if si % 50 == 0: print(si, sym, len(i), flush=True)
D = pd.concat(feats, ignore_index=True).sort_values(["bar", "sym"]).reset_index(drop=True)
for col in D.columns:
    if D[col].dtype == np.float64: D[col] = D[col].astype(np.float32)
pickle.dump({"D": D, "CF": CF, "GRID": GRID, "TPS": TPS, "SLS": SLS}, open("grid.pkl", "wb"), protocol=4)
print("готово: кандидатов", len(D), "монет", D.sym.nunique())
