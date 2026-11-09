"""Шорт на фьючерсе Binance после открытия торгов монетой к воне на Upbit или Bithumb (листинги с 01.10.2024).
Комиссия 0,1% за круг, фактический фандинг (шорт получает плюс, платит минус), стоп по максимуму 15-мин свечи.

Варианты: вход сразу (закрытие 15-мин свечи открытия), через 1, 4 и 24 ч, или после отката на 10% от максимума с
открытия (в пределах суток); держать 24/48/72/168 ч; стоп 25% или 50%. Проверка: по половинам истории, по биржам,
первый корейский листинг монеты или второй, был ли на листинге памп +15% (такие поймал бы и 🇰🇷).

Запуск из папки с данными: python3 s15/kr_short.py (нужны s15/kr_listings.pkl, s2/k2y.pkl, s2/fund2y.pkl)."""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BAR, K, fut_of, trade as sim
from kr_listings import API, get

L = pickle.load(open("s15/kr_listings.pkl", "rb"))
MK = {ex: {m["market"][4:] for m in get(f"{API[ex]}/v1/market/all") or [] if m["market"].startswith("KRW-")} for ex in API}
NEW = {(x["ex"], x["base"]) for x in L}


def old_elsewhere(x):
    """Монета уже торговалась к воне на другой корейской бирже до 01.10.2024 (рынок там есть, но не новый)."""
    other = "bithumb" if x["ex"] == "upbit" else "upbit"
    return x["base"] in MK[other] and (other, x["base"]) not in NEW


def events():
    """Листинг → событие; одна монета на обеих биржах в пределах 6 ч — одно событие (первое)."""
    ev = []
    for x in sorted(L, key=lambda x: x["t"]):
        prev = [e for e in ev if e["base"] == x["base"]]
        if prev and x["t"] - prev[-1]["t"] < 6 * 3600:
            prev[-1]["both"] = True
            continue
        ev.append(dict(x, both=False, second=bool(prev) or old_elsewhere(x)))
    return ev


def trade(e, delay_h=0, retrace=None, hold_h=48, sl=0.25, tp=None, min_age_d=1):
    s, _ = fut_of(e["base"])
    if s is None:
        return None
    a = K[s]; t = a["t"]
    if float(t[0]) > e["t"] - min_age_d * 86400:             # фьючерс моложе min_age_d — листинг Binance вместе с Кореей
        return None
    j = int(np.searchsorted(t, e["t"], side="right")) - 1   # свеча, в которой открылись торги
    if j < 8 or t[j] < e["t"] - BAR:
        return None
    i = j + int(delay_h * 4)
    if retrace is not None:                                  # ждём отката от максимума с открытия, до суток
        hi = np.maximum.accumulate(a["h"][j:j + 97].astype(float)); c = a["c"][j:j + 97].astype(float)
        k = np.flatnonzero(c <= hi * (1 - retrace))
        if not len(k):
            return None
        i = j + int(k[0])
    r = sim(s, i, tp=tp, sl=sl, hold_h=hold_h)
    if r is None:
        return None
    pump = float(a["h"][j:j + 9].max()) / float(a["c"][max(j - 1, 0)]) - 1   # памп за 2 ч с открытия
    pre = float(a["c"][j - 1]) / float(a["c"][max(j - 1 - 96, 0)]) - 1       # рост за сутки до открытия (объявление)
    return dict(r, t=e["t"], base=e["base"], sym=s, ex=e["ex"], both=e["both"], second=e["second"], pump2h=pump, pre24=pre,
                age_d=(e["t"] - float(t[0])) / 86400)


def stats(r):
    if not len(r):
        return "нет сделок"
    h = r.t < r.t.median()
    top = r.net.sort_values().iloc[:-5] if len(r) > 10 else r.net
    return (f"n={len(r):3d} | {r.net.mean() * 100:+5.1f}% на сделку (цена {r.price.mean() * 100:+5.1f}%, фандинг {r.fund.mean() * 100:+5.1f}%) | "
            f"медиана {r.net.median() * 100:+5.1f}% | в плюсе {(r.net > 0).mean():3.0%} | стопов {(r.why == 'стоп').mean():3.0%} | "
            f"1-я/2-я половина {r.net[h].mean() * 100:+5.1f}/{r.net[~h].mean() * 100:+5.1f}% | без 5 лучших {top.mean() * 100:+5.1f}%")


def run(E, **kw):
    return pd.DataFrame([x for x in (trade(e, **kw) for e in E) if x])


if __name__ == "__main__":
    E = events()
    base = run(E)
    print(f"листингов к воне с 01.10.2024: {len(L)} (Upbit {sum(x['ex'] == 'upbit' for x in L)}, Bithumb {sum(x['ex'] == 'bithumb' for x in L)}); "
          f"событий после склейки {len(E)}; с фьючерсом Binance старше суток: {len(base)}")
    print(f"\nвход сразу, 48 ч, стоп 25%: {stats(base)}")
    for name, kw in (("вход сразу, 24 ч", dict(hold_h=24)), ("вход сразу, 72 ч", dict(hold_h=72)), ("вход сразу, 168 ч", dict(hold_h=168)),
                     ("вход сразу, 48 ч, стоп 50%", dict(sl=0.5)), ("вход сразу, 48 ч, тейк 10%", dict(tp=0.10)),
                     ("через 1 ч, 48 ч", dict(delay_h=1)), ("через 4 ч, 48 ч", dict(delay_h=4)), ("через 24 ч, 48 ч", dict(delay_h=24)),
                     ("после отката 10% от максимума, 48 ч", dict(retrace=0.10)),
                     ("после отката 10%, 168 ч, стоп 50%", dict(retrace=0.10, hold_h=168, sl=0.5)),
                     ("фьючерс старше 7 дней, 48 ч", dict(min_age_d=7)), ("фьючерс старше 30 дней, 48 ч", dict(min_age_d=30))):
        print(f"  {name:38s} {stats(run(E, **kw))}")
    print("\nвход сразу, 48 ч, стоп 25% — по группам:")
    for name, m in (("Upbit", base.ex == "upbit"), ("Bithumb", base.ex == "bithumb"), ("на обеих в один день", base.both),
                    ("первый корейский листинг монеты", ~base.second), ("второй (уже торговалась на другой корейской)", base.second),
                    ("с пампом +15% за 2 ч (такие поймал бы и 🇰🇷)", base.pump2h >= 0.15), ("без пампа +15%", base.pump2h < 0.15),
                    ("рост за сутки до открытия ≥ 10%", base.pre24 >= 0.10), ("рост за сутки до открытия < 10%", base.pre24 < 0.10)):
        print(f"  {name:46s} {stats(base[m])}")
    q = base.assign(q=pd.to_datetime(base.t, unit="s").dt.to_period("Q")).groupby("q").net.agg(["size", "mean"])
    print("\nпо кварталам (вход сразу, 48 ч):", ", ".join(f"{k} {v['mean'] * 100:+.1f}% ({int(v['size'])})" for k, v in q.iterrows()))
    base.to_pickle("s15/kr_short.pkl")
