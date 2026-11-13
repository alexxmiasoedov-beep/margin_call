"""s26 — путь цены фьючерса Binance вокруг корейских событий (s26/events.pkl): призыв к осторожности («촉구»),
предупреждение («유의 종목 지정»), продление, снятие, делистинг. Одно событие одной монеты на Upbit и Bithumb в пределах
3 суток — одно событие (время — первый пост). Бар события i0 — 15-мин свеча, внутри которой вышел пост.
Доходы — шорта, простые (1 − P1/P0; + — цена упала); «к рынку» — плюс медиана простой доходности всех фьючерсов за то же
время (часовая сетка s22). Логарифмические доходности здесь не годятся: у монет с ходами ±50% они завышают доход шорта.
Плацебо — та же монета за 28, 56, 84 и 112 суток до события (без событий монеты в ±14 сут).
Запуск из папки с данными: python3 kr_study.py"""
import os
import sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s22"))
from common22 import BAR, CUT, DAY, GR, H, K, ct, live, summ, trade      # noqa: E402

E0 = pd.read_pickle("s26/events.pkl")
E0 = E0[E0.s.notna()].sort_values("ts").reset_index(drop=True)

# ------------------------------------------------------------------ объединение Upbit + Bithumb
rows = []
for (k, s), g in E0.groupby(["kind", "s"]):
    g = g.sort_values("ts")
    cur = None
    for _, r in g.iterrows():
        if cur is not None and r.ts - cur["ts"] < 3 * DAY:
            cur["exs"].add(r.ex); cur["lag"] = r.ts - cur["ts"]
            continue
        if cur is not None:
            rows.append(cur)
        cur = dict(kind=k, s=s, tok=r.tok, ts=r.ts, ex=r.ex, exs={r.ex}, end=r.end, lag=np.nan, text=r.text)
    rows.append(cur)
EV = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
EV["both"] = EV.exs.map(len) == 2

# ------------------------------------------------------------------ рынок: медиана лог-доходностей всех фьючерсов за интервал
g = GR["grid"]
with np.errstate(all="ignore"):
    LC = np.log(GR["C"].astype(np.float32))


def mkt(t0, t1):
    """Медиана простой доходности всех фьючерсов между часами, в которые попадают t0 и t1 (округление вверх до часа).
    Не накопленная сумма часовых медиан: та уходит вниз на ~3,6% в неделю относительно типичной монеты."""
    k0, k1 = np.searchsorted(g, t0), np.searchsorted(g, t1)
    if k1 >= len(g) or k0 >= len(g):
        return np.nan
    if k1 == k0:
        return 0.0
    with np.errstate(all="ignore"):
        return float(np.nanmedian(np.exp(LC[:, k1] - LC[:, k0]) - 1))


def bar_of(s, ts):
    t = K[s]["t"]; i = int(np.searchsorted(t, ts, "right") - 1)
    lo, hi = live(s)
    if i < 0 or i >= len(t) or not lo <= t[i] <= hi:
        return None
    return i


HORZ = {"15м": 1, "1ч": 4, "4ч": 16, "1д": 96, "3д": 288, "7д": 672, "14д": 1344, "30д": 2880}


def measures(s, ts, d=1):
    """Реакция от открытия бара события; дрейф шорта от закрытия бара i0 + d − 1 (d = 1: вход ≤ 15 мин после поста)."""
    i0 = bar_of(s, ts)
    if i0 is None or i0 < 2880:
        return None
    a = K[s]; c, o = a["c"].astype(float), a["o"].astype(float); t = a["t"]
    lo, hi = live(s)
    out = {}
    p0 = o[i0]
    for name, n in (("до 7д", 2688), ("до 1д", 96), ("до 4ч", 16)):
        out[name] = 1 - p0 / c[i0 - n] + mkt(t[i0 - n], t[i0])            # шорт: + если цена до события падала
    for name, n in HORZ.items():
        j = i0 + n - 1
        out["р" + name] = 1 - c[j] / p0 + mkt(t[i0], t[j] + BAR) if j < len(t) and t[j] <= hi else np.nan
    e = i0 + d - 1
    for name, n in HORZ.items():
        j = e + n
        out["д" + name] = 1 - c[j] / c[e] + mkt(t[e] + BAR, t[j] + BAR) if j < len(t) and t[j] <= hi else np.nan
    return out


def table(df, cols, label):
    print(f"\n{label}")
    for col in cols:
        x = df[col].values.astype(float); T = df.ts.values
        ok = np.isfinite(x)
        if ok.sum() < 5:
            continue
        m, t, n = ct(x[ok], T[ok]) if ok.sum() >= 10 else (np.nanmean(x), np.nan, ok.sum())
        h1 = np.nanmean(x[ok & (T < CUT)]) if (ok & (T < CUT)).sum() else np.nan
        h2 = np.nanmean(x[ok & (T >= CUT)]) if (ok & (T >= CUT)).sum() else np.nan
        print(f"  {col:7s} n={n:3d} среднее {m*100:+6.2f}% медиана {np.nanmedian(x)*100:+6.2f}% t {t:+4.1f} "
              f"шорт в плюсе {(x[ok] > 0).mean():.0%}  половины {h1*100:+.2f}/{h2*100:+.2f}% "
              f"({(ok & (T < CUT)).sum()}/{(ok & (T >= CUT)).sum()})")


if __name__ == "__main__":
    print(f"событий с фьючерсом: {len(E0)}; после объединения бирж {len(EV)}")
    print(EV.groupby("kind").agg(n=("s", "size"), both=("both", "sum"),
                                 first=("ts", lambda x: pd.Timestamp(x.min(), unit="s").strftime("%Y-%m-%d"))).to_string())
    lag = EV.lag.dropna() / 60
    print(f"разрыв между биржами, мин: медиана {lag.median():.0f}, 75% {lag.quantile(.75):.0f}")
    M = []
    for _, r in EV.iterrows():
        m = measures(r.s, r.ts)
        if m:
            M.append(dict(kind=r.kind, s=r.s, ts=r.ts, ex=r.ex, both=r.both, **m))
    M = pd.DataFrame(M)
    M.to_pickle("s26/measures.pkl")
    cols = ["до 7д", "до 1д", "до 4ч", "р15м", "р1ч", "р4ч", "р1д", "д4ч", "д1д", "д3д", "д7д", "д14д", "д30д"]
    for k in ("촉구", "предупреждение", "продление", "снятие", "делистинг"):
        table(M[M.kind == k], cols, f"=== {k} (шорт к рынку; р — от открытия бара поста, д — от входа ≤ 15 мин после поста)")
    # плацебо
    P = []
    evs = {s: EV[EV.s == s].ts.values for s in EV.s.unique()}
    for _, r in EV.iterrows():
        for k in (28, 56, 84, 112):
            tp = r.ts - k * DAY
            if np.any(np.abs(evs[r.s] - tp) < 14 * DAY):
                continue
            m = measures(r.s, tp)
            if m:
                P.append(dict(kind=r.kind, s=r.s, ts=tp, **m))
    P = pd.DataFrame(P)
    P.to_pickle("s26/placebo.pkl")
    for k in ("предупреждение", "делистинг"):
        table(P[P.kind == k], cols, f"--- плацебо к «{k}» (та же монета за 28–112 сут до события)")
