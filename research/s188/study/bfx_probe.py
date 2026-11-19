"""s188 — пробы по маржинальным позициям и ставкам займа Bitfinex (без доходов, сделок и плацебо).

Данные (bfx_fetch.py): часовые лонги и шорты маржи по парам (pos.size, в монетах, с 22.02.2021), дневные свечи ставки
займа монеты (рынок funding Bitfinex). Цена — часовые свечи Bitfinex той же пары (докачиваются здесь, кэш
/home/user/mc_data/s188/bfx/px_<пара>.json).

События-кандидаты (момент — закрытие часа; одно событие вида на монету за 72 ч):
  B1 «отдача шортов на ходе» (аналог 💸): шорты за 4 ч ≤ −20% (×0,8) при |ход цены за 4 ч| ≥ 5% и шортах ≥ порога
  (1 млн $ и 0,25 млн $);
  B2 «закрытие шортов на росте» — B1 при росте ≥ +5%; B3 — при падении ≤ −5%;
  B4 «набор шортов» (аналог З↑ s171): шорты за 24 ч ≥ ×1,5 и ≥ 1 млн $;
  B5 «шорты у максимума»: шорты ≥ 2× медианы своих 30 сут и ≥ 1 млн $ (первый час за 7 сут);
  B6 «скачок ставки займа» (аналог s40): дневная ставка ≥ 3× 10-го перцентиля своих 30 сут (первые сутки за 7 сут).
Частоты — в месяц по периодам 10.2020–09.2022 (данные pos.size с 02.2021) / 10.2022–09.2024 / 10.2024–10.2026;
пересечения — вход любого журнала по той же монете в ±72 ч (common183.journals) и наличие монеты в канале
MarginData за 24 ч до события (архив с 02.2025). Запуск: python3 -I bfx_probe.py; лог — bfx_probe.log."""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s188/bfx"
UA = {"User-Agent": "research-script/1.0"}
H = 3600
SKIP = {"BTCUSD", "USTUSD", "XAUT:USD", "LEOUSD"}
ALIAS = {"ALG": "ALGO", "BCHN": "BCH", "DSH": "DASH", "IOT": "IOTA"}


def base(p):
    b = p.replace(":USD", "").replace("USD", "")
    return ALIAS.get(b, b)


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                x = json.loads(r.read().decode())
            time.sleep(2.2)
            return x
        except Exception as e:
            print("  ошибка", url[-70:], e, flush=True)
            time.sleep(30 * (i + 1))
    return None


def prices(p):
    fn = f"{D}/px_{p.replace(':', '')}.json"
    if os.path.exists(fn):
        return json.load(open(fn))
    rows, start, t1 = [], 1612137600000, int(time.time() * 1000)
    while start < t1:
        x = get(f"https://api-pub.bitfinex.com/v2/candles/trade:1h:t{p}/hist?limit=10000&sort=1&start={start}")
        if not x:
            break
        rows += x
        if len(x) < 10000:
            break
        start = x[-1][0] + 1
    json.dump(rows, open(fn, "w"))
    return rows


def series(p):
    out = {}
    for side in ("long", "short"):
        fn = f"{D}/{p.replace(':', '')}_{side}.json"
        x = json.load(open(fn)) if os.path.exists(fn) else []
        s = pd.Series({int(t) // 1000: v for t, v in x}, dtype=float).sort_index()
        out[side] = s[~s.index.duplicated()]
    px = prices(p)
    out["px"] = pd.Series({int(r[0]) // 1000: r[2] for r in px}, dtype=float).sort_index()  # закрытие часа
    df = pd.DataFrame(out)
    df.index = (df.index // H) * H
    df = df[~df.index.duplicated()].sort_index()
    full = pd.RangeIndex(df.index.min(), df.index.max() + H, H)
    return df.reindex(full).ffill(limit=6)


def first_in(ts_list, gap):
    out, last = [], -10 ** 12
    for t in ts_list:
        if t - last >= gap:
            out.append(t)
            last = t
    return out


def main(BIG=1e6):
    pairs = [p for p in json.load(open(f"{D}/pairs.json")) if p not in SKIP]
    ev = []
    cov = []
    alln = {}
    for p in pairs:
        df = series(p)
        if df.short.notna().sum() < 1000:
            continue
        b = base(p)
        sn = df.short * df.px                       # шорты в $
        cov.append((b, df.index[df.short.notna()].min(), df.index.max(), float(sn.median())))
        alln[b] = sn
        r4 = df.px / df.px.shift(4) - 1
        s4 = df.short / df.short.shift(4)
        s24 = df.short / df.short.shift(24)
        med30 = df.short.rolling(24 * 30, min_periods=24 * 20).median()
        big = sn >= BIG
        cond = {
            "B1": (s4 <= 0.8) & (r4.abs() >= 0.05) & big.shift(4).fillna(False).astype(bool),
            "B2": (s4 <= 0.8) & (r4 >= 0.05) & big.shift(4).fillna(False).astype(bool),
            "B3": (s4 <= 0.8) & (r4 <= -0.05) & big.shift(4).fillna(False).astype(bool),
            "B4": (s24 >= 1.5) & big,
            "B5": (df.short >= 2 * med30) & big,
        }
        for k, c in cond.items():
            gap = 7 * 86400 if k == "B5" else 72 * H
            for t in first_in(list(df.index[c.fillna(False).astype(bool)]), gap):
                ev.append((k, b, int(t), float(sn.get(t, np.nan))))
        # B6: ставка займа монеты (дневные свечи funding: [mts, open, close, high, low, volume])
        fn = f"{D}/funding_{p.replace(':USD', '').replace('USD', '')}.json"
        if os.path.exists(fn):
            f = json.load(open(fn)) or []
            fr = pd.Series({int(r[0]) // 1000: r[2] for r in f}, dtype=float).sort_index()
            if len(fr) > 60:
                fl = fr.rolling(30, min_periods=20).quantile(0.10).shift(1)
                c6 = (fr >= 3 * fl) & (fl > 0)
                for t in first_in(list(fr.index[c6.fillna(False).astype(bool)]), 7 * 86400):
                    ev.append(("B6", b, int(t), np.nan))
    E = pd.DataFrame(ev, columns=["k", "s", "t", "usd"])
    E.to_pickle(f"/home/user/mc_data/s188/bfx_events_{int(BIG)}.pkl")
    print(f"\n######## порог шортов {BIG / 1e6:g} млн $")
    print("Охват (монета, шорты с, до, медиана шортов в $):")
    for b, t0, t1, m in sorted(cov, key=lambda z: -z[3]):
        print(f"  {b:<6} {time.strftime('%Y-%m-%d', time.gmtime(t0))} … {time.strftime('%Y-%m-%d', time.gmtime(t1))}"
              f"  {m / 1e6:8.1f} млн $")
    A = pd.DataFrame(alln)
    yr = pd.to_datetime(A.index, unit="s").year
    alts = [c for c in A.columns if c != "ETH"]
    print("Шорты маржи Bitfinex, медиана по часам, млн $ (альты — сумма по монетам):")
    for y, g in A.groupby(yr):
        print(f"  {y}: альты {g[alts].sum(axis=1, min_count=1).median() / 1e6:7.2f}; ETH {g['ETH'].median() / 1e6:8.2f}"
              if "ETH" in g else f"  {y}: альты {g[alts].sum(axis=1, min_count=1).median() / 1e6:7.2f}")
    mg = pd.read_pickle("/home/user/mc_data/s7/margin.pkl")["G"]
    for per in C.PERS:
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        J = C.journals(per)
        jt = {s: np.sort(x.t.values) for s, x in J.groupby("s")}
        mon = C.months(per)
        print(f"\n== {per}")
        for k in ("B1", "B2", "B3", "B4", "B5", "B6"):
            x = E[(E.k == k) & (E.t >= t0) & (E.t < t1)]
            if not len(x):
                print(f"  {k}: событий нет")
                continue
            span = (min(t1, x.t.max() + 1) - max(t0, 1614000000 if k != "B6" else t0)) / (30.4 * 86400)
            ovj = np.mean([len(jt.get(s, [])) > 0 and np.any(np.abs(jt[s] - t) <= 72 * H) for s, t in zip(x.s, x.t)])
            inmd = []
            for s, t in zip(x.s, x.t):
                a = mg.get(s)
                inmd.append(a is not None and np.any((a[:, 0] <= t) & (a[:, 0] > t - 86400)))
            md = f"; монета в канале MarginData за 24 ч: {np.mean(inmd):.0%}" if t1 > 1740000000 else ""
            print(f"  {k}: {len(x)} событий, {len(x) / max(span, 1):.1f} в месяц (за {span:.0f} мес. с данными), "
                  f"монет {x.s.nunique()}, вход журнала ±72 ч {ovj:.0%}{md}; чаще всех: "
                  + ", ".join(f"{s} {n}" for s, n in x.s.value_counts().head(5).items()))


if __name__ == "__main__":
    for big in (1e6, 2.5e5):
        main(big)
