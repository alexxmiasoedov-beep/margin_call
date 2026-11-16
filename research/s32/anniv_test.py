"""s32 — шорт вокруг годовщины запуска фьючерса Binance («скрытый годовой cliff»; гипотезы — ВЫВОДЫ.md, записаны до
проверки). Запуск — первая 15-мин свеча с объёмом (s2/k2y.pkl), только фьючерсы, запущенные позже 03.10.2024.
Г1: шорт с A − 7 сут до A + 1 сут (A = запуск + 365 сут), стоп +50%, без тейка, комиссия 0,1%, фактический фандинг
(s15/common.trade); плацебо — те же окна на 45/90/135 сут раньше; половины до и после 01.12.2025; пересечение с
разлоками CMC из s28/trades.pkl (±7 сут от A). Г2: окна A − 14 → A, A → A + 14, полгода (запуск + 182 сут, −7 / +1).
Итог — s32/trades.pkl. Запуск из папки с данными."""
import datetime
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import K, live, trade  # noqa: E402

DAY = 86400
CUT = 1764547200
PL = (45, 90, 135)
START = datetime.datetime(2024, 10, 3, tzinfo=datetime.timezone.utc).timestamp()
SKIP = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD", "USDBRL",
        "BTCDOM", "DEFI", "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "COPPER", "CL", "BZ", "AAPL", "AMD", "AMZN", "COIN",
        "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA"}


def idx(s, te):
    """Индекс 15-мин свечи, закрывающейся не позже te (ближайшая)."""
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900, "right")) - 1
    return i if i >= 0 else None


def short(s, t_in, t_out):
    i = idx(s, t_in)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=(t_out - t_in) / 3600, side=-1)
    return r["net"] if r else None


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


def run(age_d, a, b, U):
    """Окно [A + a, A + b] сут, A = запуск + age_d сут; плацебо — то же окно на 45/90/135 сут раньше."""
    rows = []
    for s, l0, ov in U:
        A = l0 + age_d * DAY
        t_in, t_out = A + a * DAY, A + b * DAY
        n = short(s, t_in, t_out)
        if n is None:
            continue
        p = [short(s, t_in - d * DAY, t_out - d * DAY) for d in PL]
        p = [x for x in p if x is not None]
        rows.append(dict(s=s, te=t_in, net=n, plac=np.mean(p) if p else np.nan, ov=ov(A)))
    return pd.DataFrame(rows)


def show(D, label):
    for lab, x in (("все", D), ("без разлоков CMC ±7 сут", D[~D.ov])):
        m, t, n = ct(x.net, x.te)
        h1, h2 = x[x.te < CUT].net, x[x.te >= CUT].net
        print(f"  {label}, {lab}: n={n} {m:+.2%} (t {t:+.1f}), медиана {x.net.median():+.2%}, в плюсе {(x.net > 0).mean():.0%}, "
              f"стопов {(x.net < -0.45).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | "
              f"плацебо {x.plac.mean():+.2%} → разница {(x.net - x.plac).mean():+.2%}", flush=True)


if __name__ == "__main__":
    UL = pd.read_pickle("s28/trades.pkl")[["s", "t"]].drop_duplicates()
    ul = {s: g.t.values for s, g in UL.groupby("s")}
    U = []
    for s in K:
        if s in SKIP:
            continue
        l0, l1 = live(s)
        if not np.isfinite(l0) or l0 <= START:
            continue
        U.append((s, l0, (lambda A, s=s: bool(len(ul.get(s, [])) and (np.abs(ul[s] - A) <= 7 * DAY).any()))))
    print(f"фьючерсов, запущенных после 03.10.2024: {len(U)}")
    res = {}
    for key, (age, a, b) in {"Г1: A−7 → A+1": (365, -7, 1), "A−14 → A": (365, -14, 0), "A → A+14": (365, 0, 14),
                             "полгода −7 → +1": (182, -7, 1)}.items():
        D = run(age, a, b, U); res[key] = D
        show(D, key)
    pickle.dump(res, open("s32/trades.pkl", "wb"))
