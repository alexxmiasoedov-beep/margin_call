"""s234 — признаки входа сделок виртуальных журналов из открытых данных Binance (www.binance.com/fapi):
- ставка последнего начисления фандинга до входа, в пересчёте на 8 ч (fundingRate);
- возраст фьючерса на входе, сут (exchangeInfo onboardDate);
- ход монеты за 1, 4, 24 ч и 7 сут до входа (часовые свечи), волатильность часовых ходов за 7 сут;
- ход BTC за 24 ч до входа; час и день недели входа.
Итог — s234/feat.pkl. Запуск из /home/user/mc_data: python3 <repo>/research/s234/entry_features.py"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

UA = {"User-Agent": "research-script/1.0"}
H = 3600


def get(url):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2 * (k + 1))
    return None


def main():
    D = pd.read_pickle("s234/trades_1711.pkl")
    info = get("https://www.binance.com/fapi/v1/exchangeInfo")
    onboard = {x["symbol"]: x.get("onboardDate", 0) / 1000 for x in info["symbols"]} if info else {}
    syms = sorted(set(D.s))
    t0 = int(D.t.min()) - 40 * 86400; t1 = int(D.t.max()) + 3600

    def fund(s):
        out, st = [], t0 * 1000
        while True:
            j = get(f"https://www.binance.com/fapi/v1/fundingRate?symbol={s}USDT&startTime={st}&endTime={t1 * 1000}&limit=1000")
            if not j:
                break
            out += [(x["fundingTime"] / 1000, float(x["fundingRate"])) for x in j]
            if len(j) < 1000:
                break
            st = j[-1]["fundingTime"] + 1
        return s, np.array(out) if out else np.zeros((0, 2))

    def kl(s):
        rows, st = [], t0 * 1000
        while st < t1 * 1000:
            j = get(f"https://www.binance.com/fapi/v1/klines?symbol={s}USDT&interval=1h&startTime={st}&endTime={t1 * 1000}&limit=1500")
            if not j:
                break
            rows += [[x[0] / 1000, float(x[4])] for x in j]
            if len(j) < 1500:
                break
            st = j[-1][0] + H * 1000
        return s, np.array(rows) if rows else np.zeros((0, 2))
    with ThreadPoolExecutor(4) as ex:
        F = dict(ex.map(fund, syms))
        K = dict(ex.map(kl, syms + ["BTC"]))
    rows = []
    for r in D.itertuples():
        f = F.get(r.s, np.zeros((0, 2))); k = K.get(r.s, np.zeros((0, 2))); b = K.get("BTC")
        rec = {"j": r.j, "t": r.t, "s": r.s}
        prev = f[f[:, 0] <= r.t] if len(f) else f
        if len(prev):
            dt = np.diff(prev[-2:, 0])[0] / H if len(prev) >= 2 else 8.0
            rec["f8"] = prev[-1, 1] * 8 / max(dt, 1.0)               # последняя ставка в пересчёте на 8 ч
            rec["fint"] = dt
        ob = onboard.get(f"{r.s}USDT", 0)
        rec["age"] = (r.t - ob) / 86400 if ob else np.nan

        def ch(a, h):
            i = np.searchsorted(a[:, 0], r.t - 3600, "right") - 1      # последняя полностью закрытая часовая свеча
            j = np.searchsorted(a[:, 0], r.t - 3600 - h * H, "right") - 1
            return a[i, 1] / a[j, 1] - 1 if i >= 0 and j >= 0 and i > j else np.nan
        if len(k):
            for h in (1, 4, 24, 168):
                rec[f"r{h}"] = ch(k, h)
            i = np.searchsorted(k[:, 0], r.t - 3600, "right")
            w = k[max(0, i - 168):i, 1]
            rec["vol7"] = np.std(np.diff(np.log(w))) * np.sqrt(24) if len(w) > 24 else np.nan
        if b is not None and len(b):
            rec["btc24"] = ch(b, 24)
        rec["hour"] = int(r.t // H % 24); rec["wday"] = int((r.t // 86400 + 3) % 7)    # 0 — понедельник
        rows.append(rec)
    pd.DataFrame(rows).to_pickle("s234/feat.pkl")
    print(f"признаки: {len(rows)} сделок, монет {len(syms)}; без фандинга {sum(1 for x in rows if 'f8' not in x)}, "
          f"без возраста {sum(1 for x in rows if not np.isfinite(x.get('age', np.nan)))}")


if __name__ == "__main__":
    main()
