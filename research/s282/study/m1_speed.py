"""s282 — как быстро достигается минимум (максимум) в свече-событии: выборка минутных свечей data.binance.vision.

Берутся только минуты ДО минимума (максимума) включительно: открытие, минимум (у роста — максимум) и закрытия минут перед
ним. Закрытие минуты с минимумом, всё после минимума, «откат», доход лимитки не считаются (запрет записи до расчёта s283).

События — wicks_build.py: перп ≥ 7 сут, первое у монеты за 24 ч в своей стороне, порог X = 5% и 10%;
случайная выборка до N на период, сторону и порог (зерно 282). Для каждой: минуты свечи [T, T + 15 мин) и последняя
минута прошлой свечи. Мера по закрытию прошлой 15-мин свечи c0 и уровню L = c0·(1 − X) (у роста c0·(1 + X)):
- m_touch — первая минута (0…14), где минимум минуты ≤ L; m_low — минута минимума свечи;
- pre — сколько пути до L цена прошла к закрытию минуты перед касанием (0 — касание из спокойствия, 1 — уже у уровня);
- one — касание одной минутой: минимум минуты касания ≤ закрытие прошлой минуты × (1 − X)
  (то есть лимитку на −X от последней минутной цены тоже бы задело);
- m_half — первая минута, где цена прошла половину пути (≤ c0·(1 − X/2)); спуск = m_touch − m_half.
Минутные окна — /dev/shm/s282/m1_<период>.pkl, таблица мер — /home/user/mc_data/s282/m1_speed.csv.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s282/study/m1_speed.py [N]"""
import io
import os
import pickle
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common282 import BAR, DAY, OUT, PER, TMP, TURN_BINS, cooldown_mask  # noqa: E402

M = 60
UA = "research-script/1.0"
BASE = "https://data.binance.vision/data/futures/um/daily/klines"


def fetch_day(sym, day):
    """Минутные свечи перпа за сутки UTC: массив [t откр., o, h, l, c] или None."""
    d = pd.Timestamp(day * DAY, unit="s").strftime("%Y-%m-%d")
    url = f"{BASE}/{sym}USDT/1m/{sym}USDT-1m-{d}.zip"
    for k in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, "-w", "%{http_code}", "-o", "-", url], capture_output=True)
        code = r.stdout[-3:].decode(errors="ignore")
        if code == "404":
            return None
        if code == "200":
            try:
                z = zipfile.ZipFile(io.BytesIO(r.stdout[:-3]))
                rows = [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines()]
                a = np.array([[int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4])]
                              for p in rows if p and p[0][:1].isdigit()])
                if len(a) and a[0, 0] > 10 ** 11:            # отметки в микросекундах (новые файлы архива)
                    a[:, 0] //= 1000
                return a if len(a) else None
            except (zipfile.BadZipFile, ValueError, IndexError):
                pass
        time.sleep(2 + 2 * k)
    return None


def window(sym, T):
    """Минуты с открытием в [T − 1 мин, T + 15 мин): последняя минута прошлой свечи и вся свеча события."""
    days = sorted({(T - M) // DAY, (T + 14 * M) // DAY})
    parts = [x for x in (fetch_day(sym, d) for d in days) if x is not None]
    if not parts:
        return None
    a = np.concatenate(parts)
    a = a[(a[:, 0] >= T - M) & (a[:, 0] < T + 15 * M)]
    return a[np.argsort(a[:, 0])] if len(a) else None


def measures(a, T, c0, x, side, bar_ext):
    """Меры скорости до минимума (side −1) или максимума (+1). None — минут не хватает или не сходится с 15-мин свечой."""
    t = a[:, 0].astype(np.int64)
    if len(t) != 16 or t[0] != T - M or np.any(np.diff(t) != M):
        return None
    o, h, l, c = a[1:, 1], a[1:, 2], a[1:, 3], a[1:, 4]
    c_prev_min = np.r_[a[0, 4], c[:-1]]                 # закрытие минуты перед каждой минутой свечи
    if side < 0:
        ext = l
        lvl = c0 * (1 - x)
        hit = ext <= lvl * (1 + 1e-6)
        half = ext <= c0 * (1 - x / 2) * (1 + 1e-6)
        e_bar = ext.min()
        ok = abs(e_bar / bar_ext - 1) < 2e-4
    else:
        ext = h
        lvl = c0 * (1 + x)
        hit = ext >= lvl * (1 - 1e-6)
        half = ext >= c0 * (1 + x / 2) * (1 - 1e-6)
        e_bar = ext.max()
        ok = abs(e_bar / bar_ext - 1) < 2e-4
    if not hit.any() or not ok:
        return None
    mt = int(np.argmax(hit))
    ml = int(np.argmax(ext == e_bar))
    mh = int(np.argmax(half))
    ref = c_prev_min[mt]
    pre = (1 - ref / c0) / x if side < 0 else (ref / c0 - 1) / x
    one = ext[mt] <= ref * (1 - x) if side < 0 else ext[mt] >= ref * (1 + x)
    dmin = (1 - ext[mt] / o[mt]) if side < 0 else (ext[mt] / o[mt] - 1)     # ход внутри минуты касания от её открытия
    return dict(m_touch=mt, m_low=ml, m_half=mh, pre=pre, one=bool(one), dmin=dmin, gap0=a[0, 4] / c0 - 1)


def main(N=250):
    rng = np.random.default_rng(282)
    rows = []
    for per, cfg in PER.items():
        E = pd.read_pickle(f"{TMP}/ev_{per}.pkl")
        E = E[E.age >= 7]
        B = dict(np.load(f"{TMP}/bars_{per}.npz"))
        # закрытие прошлой свечи и экстремум свечи — по 15-мин данным
        K = pickle.load(open(cfg["k"], "rb"))
        sample = []
        for side in (-1, 1):
            for xi, x in ((1, 0.05), (3, 0.10)):
                d = -E.dl.values if side < 0 else E.dh.values
                F = E[d >= x]
                k24 = cooldown_mask(F.s.cat.codes.values, F.t.values, DAY)
                F = F[k24]
                take = rng.choice(len(F), size=min(N, len(F)), replace=False)
                for r in F.iloc[np.sort(take)].itertuples():
                    gi = int((r.t - cfg["t0"]) // BAR)
                    cnt = (B["cnt_dn7"] if side < 0 else B["cnt_up7"])[xi][gi]
                    share = cnt / max(B["live7"][gi], 1)
                    cls = 0 if cnt <= 1 else 1 if cnt <= 4 else 2 if share < 0.10 else 3
                    sample.append((r.s, int(r.t), side, x, r.turn, cls))
        f = f"{TMP}/m1_{per}.pkl"
        W = pickle.load(open(f, "rb")) if os.path.exists(f) else {}
        todo = sorted({(s, t) for s, t, *_ in sample if (s, t) not in W})
        print(per, "событий в выборке", len(sample), "минутных окон докачать", len(todo), flush=True)
        with ThreadPoolExecutor(8) as ex:
            for n, (key, a) in enumerate(zip(todo, ex.map(lambda k: window(*k), todo))):
                W[key] = a
                if n % 400 == 399:
                    pickle.dump(W, open(f, "wb"))
                    print("  ", n + 1, flush=True)
        pickle.dump(W, open(f, "wb"))
        for s, T, side, x, turn, cls in sample:
            a = W.get((s, T))
            if a is None:
                rows.append(dict(per=per, s=s, t=T, side=side, x=x, turn=turn, cls=cls, status="нет минут"))
                continue
            k = K[s]
            i = int(np.searchsorted(k["t"], T))
            c0 = float(k["c"][i - 1])
            ext = float(k["l"][i] if side < 0 else k["h"][i])
            m = measures(a, T, c0, x, side, ext)
            rows.append(dict(per=per, s=s, t=T, side=side, x=x, turn=turn, cls=cls,
                             status="ок" if m else "не сходится", **(m or {})))
        del K
    D = pd.DataFrame(rows)
    D.to_csv(f"{OUT}/m1_speed.csv", index=False)
    print(D.groupby(["per", "side", "x"]).status.value_counts().unstack(fill_value=0))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 250)
