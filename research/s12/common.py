"""Общие данные для s12: свечи и фандинг фьючерсов, канал MarginData, TradFi-исключения, объявления о спотовых листингах."""
import pickle, re, datetime
import numpy as np
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
kind = pickle.load(open("s12/perp_kind.pkl", "rb"))
TF = kind["tradfi"] | {"BZ", "CL", "COPPER", "NATGAS", "XAG", "XPD", "XPT", "XAU", "GIGADEV", "POPMART", "QNTX", "SPCX", "USDBRL"}
_m = pickle.load(open("s7/margin.pkl", "rb")); G = _m["G"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for _c, _arr in G.items(): ch.setdefault(strip(_c), []).append(np.unique(_arr[:, 0]))
ch = {k: np.unique(np.concatenate(v)) for k, v in ch.items()}
UTC = datetime.timezone.utc
T_START = datetime.datetime(2024, 10, 5, tzinfo=UTC).timestamp(); T_END = datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp()
CH0 = datetime.datetime(2025, 2, 21, tzinfo=UTC).timestamp()
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
btc = K["BTC"]
def fsum(s, a, b):
    f = FU.get(s)
    return 0.0 if f is None else float(f[(f[:, 0] > a) & (f[:, 0] <= b), 2].sum())
def px(a, t):
    j = int(np.searchsorted(a["t"], int(t // 900 * 900))); j = min(j, len(a["t"]) - 1); return float(a["o"][j]), j
def fnow(s, t):
    f = FU.get(s)
    if f is None: return None
    k = np.searchsorted(f[:, 0], t, "right") - 1
    return float(f[k, 2] / f[k, 1] * 8) if k >= 0 else None
A = pickle.load(open("s10/ann.pkl", "rb"))
spot_ann = {}
for _a in A.values():
    if not _a["ts"]: continue
    _mm = re.search(r"Binance Will List (.+?)\s*\(([A-Z0-9]+)\)", _a["title"]) or re.search(r"Introducing .*?\(([A-Z0-9]+)\) on Binance (?:HODLer|Launchpool|Megadrop)", _a["title"])
    if _mm:
        spot_ann.setdefault(_mm.group(_mm.lastindex), _a["ts"] // 1000)
