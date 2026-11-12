"""Г10. События маржи Binance (Chang, Luo & Ren: допуск к шорту в Китае → отрицательная доходность; Hsieh & Miller:
изменения маржинальных требований следуют за волатильностью). Три типа:
  а) займ открыт: первая запись ставки займа монеты в публичной истории (s11/rates, с 01.09.2024; активы, у которых
     история начинается в первые 15 суток, — уже были в марже, не считаются) → шорт перпа на 7/14/30 суток;
     контроль — фьючерсы того же возраста (от начала торгов, ±50%) в тот же час: у новых монет общий дрейф вниз;
  б) делистинг маржинальных пар (заголовки «Binance Margin … Will Delist A, B …», s10/ann.pkl) → обе стороны;
  в) обновление ступеней плеча фьючерсов («Update on the Margin Tiers…», тексты статей Binance, кэш s22/ann_text.pkl):
     снижение максимального плеча или лимита позиции → шорт на 7 суток; повышение — контроль.
Исход — доход шорта к рынку (медиана фьючерсов) и к монетам той же волатильности за 7 суток (квинтиль ±0,1), с фандингом;
t — с кластеризацией по дню (пакетные объявления — одна дата). Запуск из папки с данными."""
import json
import os
import pickle
import re
import subprocess
import sys
import time
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import DAY, GR, H, K, NONCRYPTO, ct, fut_of, fwd, live, summ

DET = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={}"


def texts(code, cache):
    if code in cache:
        return cache[code]
    for k in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "30", DET.format(code)], capture_output=True, text=True).stdout
        try:
            b = (json.loads(r).get("data") or {}).get("body") or ""
            out = []
            def walk(o):
                if isinstance(o, dict):
                    if isinstance(o.get("text"), str):
                        out.append(o["text"])
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
            walk(json.loads(b)); cache[code] = out; time.sleep(0.3)
            return out
        except Exception:
            time.sleep(3 + 5 * k)
    return None


LEV = re.compile(r"^\s*(?:(\d+)\s*-\s*)?(\d+)\s*x\s*$")
POS = re.compile(r"Position\s*(?:≤|&lt;=|<=)\s*([\d,]+)")
PCT = re.compile(r"^\s*[\d.]+\s*%\s*$")


def tiers(tx):
    """Разделы «дата (UTC): СИМВОЛЫ (USDⓈ-M …)» и таблица до/после → [(время, [символы], макс. плечо до/после, лимит до/после)]."""
    out, i = [], 0
    while i < len(tx):
        m = re.match(r"\s*(\d{4}-\d\d-\d\d \d\d:\d\d) \(UTC\)", tx[i])
        if not m:
            i += 1; continue
        syms = re.findall(r"\b([A-Z0-9]{2,20})USDT\b", tx[i + 1] if i + 1 < len(tx) else "")
        j = i + 2
        while j < len(tx) and "Maintenance Margin Rate After Change" not in tx[j]:
            if re.match(r"\s*\d{4}-\d\d-\d\d \d\d:\d\d \(UTC\)", tx[j]):
                break
            j += 1
        j += 1; side = 0; bl, bp, al, ap = [], [], [], []
        while j < len(tx):
            c = tx[j].strip()
            if c == "NA":
                side ^= 1; j += 1; continue
            lm = LEV.match(c)
            if lm and j + 2 < len(tx) and POS.search(tx[j + 1].replace("&lt;", "<")) is not None and PCT.match(tx[j + 2]):
                pv = int(POS.search(tx[j + 1].replace("&lt;", "<")).group(1).replace(",", ""))
                (bl if side == 0 else al).append(int(lm.group(2))); (bp if side == 0 else ap).append(pv)
                side ^= 1; j += 3; continue
            break
        if syms and bl and al:
            out.append((m.group(1), syms, max(bl), max(al), max(bp), max(ap)))
        i = max(j, i + 1)
    return out


def matched(T, s, h, mode):
    """Доход шорта s к рынку минус средний доход шорта к рынку у фьючерсов-сверстников (возраст ±50%) или той же
    волатильности за 7 суток (±0,1 по рангу) в тот же час."""
    g, C = GR["grid"], GR["C"]; k = int(np.searchsorted(g, T))
    if k + h >= len(g) or g[k] != T:
        return np.nan
    R = 1 - C[:, k + h] / C[:, k]
    me = R[GR["row"][s]]
    if not np.isfinite(me):
        return np.nan
    if mode == "age":
        ages = np.array([(T - live(x)[0]) / DAY for x in GR["syms"]])
        a0 = (T - live(s)[0]) / DAY
        band = (ages >= a0 * 0.5) & (ages <= a0 * 1.5) & np.isfinite(R)
    else:
        lr = np.log(C[:, max(k - 168, 1):k + 1]); rv = np.nanstd(np.diff(lr, axis=1), axis=1)
        q = pd.Series(rv).rank(pct=True).values
        band = np.isfinite(R) & np.isfinite(q) & (np.abs(q - q[GR["row"][s]]) <= 0.1)
    band[GR["row"][s]] = False
    return me - np.nanmean(R[band]) if band.sum() >= 5 else np.nan


def report(nm, E, modes=("vol",)):
    print(f"\n{nm}: {len(E)} событий, дат {pd.to_datetime(E['T'], unit='s').dt.date.nunique()}")
    for h in (168, 336, 720):
        x = np.array([fwd(s, T, h) for s, T in zip(E.s, E["T"])])
        xn = np.array([fwd(s, T, h, net=True) for s, T in zip(E.s, E["T"])])
        line = f"  {h // 24:2d} сут: шорт к рынку {summ(x, E['T'].values)} | с фандингом {np.nanmean(xn) * 100:+.2f}%"
        for md in modes:
            xm = np.array([matched(T, s, h, md) for s, T in zip(E.s, E["T"])])
            line += f" | к {'сверстникам' if md == 'age' else 'той же волатильности'} {np.nanmean(xm) * 100:+.2f}% (t {ct(xm, E['T'].values)[1]:+.1f})"
        print(line)


def hour_up(t):
    return int((t // H + 1) * H)


if __name__ == "__main__":
    g = GR["grid"]
    rows = []
    for f in os.listdir("s11/rates"):
        a = f[:-4]
        if a in NONCRYPTO:
            continue
        try:
            t0 = float(open(f"s11/rates/{f}").readline().split(",")[0])
        except (ValueError, IndexError):
            continue
        s, _ = fut_of(a)
        if s is None or t0 < 1725148800 + 15 * DAY or s not in GR["row"]:
            continue
        T = hour_up(t0)
        if T - 900 < live(s)[0] + DAY or T > g[-1] - 30 * DAY:
            continue
        rows.append(dict(s=s, T=T, age=(T - live(s)[0]) / DAY))
    EA = pd.DataFrame(rows)
    print(f"а) займ открыт: {len(EA)} монет; возраст фьючерса к открытию займа: медиана {EA.age.median():.0f} суток")
    report("а) займ открыт, шорт перпа", EA, modes=("age", "vol"))
    for nm, m in (("а) займ открыт, фьючерсу ≤ 30 суток", EA.age <= 30), ("а) займ открыт, фьючерсу > 30 суток", EA.age > 30)):
        report(nm, EA[m], modes=("age",))

    A = pd.read_pickle("s10/ann.pkl")
    T = sorted((int(a["ts"]) / 1000, a["title"], a["code"]) for a in A.values())
    rows = []
    for ts, title, code in T:
        if not re.search(r"Margin.*Will Delist", title) or "Futures" in title or ts < g[0] + DAY:
            continue
        part = re.split(r"Will Delist", title)[1]
        for c in re.findall(r"\b([A-Z0-9]{2,12})\b", part.split(" on ")[0]):
            s, _ = fut_of(c)
            if s and s in GR["row"] and live(s)[0] < ts - DAY and live(s)[1] > ts + 7 * DAY:
                rows.append(dict(s=s, T=hour_up(ts)))
    EB = pd.DataFrame(rows).drop_duplicates()
    report("б) делистинг маржинальных пар (знак «+» — шорт выигрывает)", EB)

    cache = pickle.load(open("s22/ann_text.pkl", "rb")) if os.path.exists("s22/ann_text.pkl") else {}
    rows = []
    tier_ann = [(ts, code) for ts, title, code in T if re.search(r"Margin Tiers", title) and ts >= g[0]]
    print(f"\nобъявлений о ступенях плеча с 10.2024: {len(tier_ann)}", flush=True)
    for ts, code in tier_ann:
        tx = texts(code, cache)
        if not tx:
            continue
        for when, syms, lb, la, pb, pa in tiers(tx):
            for c in syms:
                s = c if c in GR["row"] else None
                if s is None or not (live(s)[0] < ts - DAY and live(s)[1] > ts + 7 * DAY):
                    continue
                rows.append(dict(s=s, T=hour_up(ts), lb=lb, la=la, pb=pb, pa=pa))
    pickle.dump(cache, open("s22/ann_text.pkl", "wb"))
    EC = pd.DataFrame(rows).drop_duplicates(["s", "T"])
    print(f"в) символо-событий: {len(EC)}; плечо снижено у {(EC.la < EC.lb).sum()}, повышено у {(EC.la > EC.lb).sum()}; "
          f"лимит позиции снижен у {(EC.pa < EC.pb).sum()}, повышен у {(EC.pa > EC.pb).sum()}")
    down = (EC.la < EC.lb) | ((EC.la == EC.lb) & (EC.pa < EC.pb))
    up = (EC.la > EC.lb) | ((EC.la == EC.lb) & (EC.pa > EC.pb))
    report("в) снижение плеча или лимита позиции", EC[down])
    report("в) повышение (контроль)", EC[up])
    EA.to_pickle("s22/h10_a.pkl"); EB.to_pickle("s22/h10_b.pkl"); EC.to_pickle("s22/h10_c.pkl")
