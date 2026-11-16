"""s29 — события «садок»: Upbit или Bithumb закрыл ввод монеты, у которой есть фьючерс Binance.
Уведомления — s26/tg_upbit_news.json (Telegram upbit_news) и s26/tg_bithumb_notice.json (зеркало bithumb_notice).
По каждому посту о вводе-выводе: монеты из «(ТИКЕР)», тип (ввод и вывод / только ввод / только вывод), начало (время из
заголовка, время Кореи, или время поста) или конец («(완료)», «재개», «정상화»). Посты одной монеты на одной бирже
склеиваются в закрытия: начало → ближайший конец; без конца за 30 сут — конец неизвестен.
Премия монеты на бирже по часам: закрытие в вонах · множитель / закрытие USDT-KRW той же биржи / закрытие фьючерса
Binance − 1; час берётся, если оборот монеты на бирже ≥ 10 тыс. $ (s15/kr_candles_<биржа>.pkl, s22/grid.pkl).
Итог — s29/cages.pkl: таблица событий с путём премии. Доходы фьючерса здесь не считаются.
Запуск из папки с данными: python3 cage_events.py"""
import datetime
import json
import os
import pickle
import re
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import fut_of, live  # noqa: E402

KST = 9 * 3600
DAY = 86400
T0 = datetime.datetime(2024, 10, 2, tzinfo=datetime.timezone.utc).timestamp()
T1 = datetime.datetime(2026, 10, 11, tzinfo=datetime.timezone.utc).timestamp()
MIN_USD = 10_000
SRC = {"upbit": "s26/tg_upbit_news.json", "bithumb": "s26/tg_bithumb_notice.json"}
GR = pickle.load(open("s22/grid.pkl", "rb"))
G, CB, ROW = GR["grid"], GR["C"].astype(np.float64), GR["row"]
KC = {ex: pickle.load(open(f"s15/kr_candles_{ex}.pkl", "rb")) for ex in SRC}

TICK = re.compile(r"\(([A-Z0-9]{1,12})\)")
DT = re.compile(r"(\d{1,2})\s*(?:/|\.|월)\s*(\d{1,2})\s*일?\s*(오전|오후)?\s*(\d{1,2})\s*(?::\s*(\d{2})|시\s*(?:(\d{1,2})\s*분)?)")


def title(text):
    return text.split("http")[0].split("🔗")[0].strip()


def tail(t):
    m = re.search(r"\(([^()]*)\)\s*$", t)
    return m.group(1).strip() if m else ""


def kst_time(s, post):
    """Дата и время из строки (время Кореи) → UTC, с; год — от поста (месяц на полгода раньше — следующий год)."""
    m = DT.search(s)
    if not m:
        return None
    mo, d, ap, h, mi1, mi2 = m.groups()
    h = int(h); mi = int(mi1 or mi2 or 0)
    if ap == "오후" and h < 12:
        h += 12
    if ap == "오전" and h == 12:
        h = 0
    pd_ = datetime.datetime.fromtimestamp(post, datetime.timezone.utc)
    y = pd_.year + (1 if int(mo) < pd_.month - 6 else 0)
    try:
        return datetime.datetime(y, int(mo), int(d), h % 24, mi, tzinfo=datetime.timezone.utc).timestamp() - KST
    except ValueError:
        return None


def parse(ex, post, text):
    """Пост → список (монета, событие) или []: событие = dict(kind=start|end, t, typ, tag, title)."""
    t = title(text)
    if not re.search(r"입출금|입금|출금", t):
        return []
    if re.search(r"계열|\d+\s*종|정기실사|서버 점검|특정금융정보법|개시|신규 발급", t):
        return []                                            # массовые закрытия, общие работы, открытие нового рынка
    coins = list(dict.fromkeys(TICK.findall(t)))
    if not coins or len(coins) > 3:
        return []
    typ = "both" if "입출금" in t else "dep" if "입금" in t else "wd"
    tl = tail(t)
    tag = ("warn" if "유의" in t else "migr" if re.search(r"스왑|리브랜딩|메인넷|전환|컨트랙트|마이그레이션", t)
           else "drop" if re.search(r"에어드랍|스냅샷", t) else "net")
    end = (tl == "완료" or tl == "정상화" or "취소" in tl
           or ("재개" in tl and not (tl.startswith("출금") and "입출금" not in tl))
           or (re.search(r"재개\s*안내$", t) and not re.search(r"중단|중지", t)))
    if end:
        return [(c, dict(kind="end", t=post, typ=typ, tag=tag, title=t)) for c in coins]
    if not re.search(r"중단|중지|지연|순단", t):
        return []
    st = kst_time(tl, post) if ("~" in tl or "예정" in tl) else None
    return [(c, dict(kind="start", t=st if st and st > post - DAY else post, sched=st is not None, post=post, typ=typ,
                     tag=tag, title=t)) for c in coins]


def events():
    rows = []
    for ex, path in SRC.items():
        seen = {}
        posts = []
        for _, ts, text in json.load(open(path)):
            post = datetime.datetime.fromisoformat(ts).timestamp()
            for c, e in parse(ex, post, text):
                key = (c, e["kind"], e["title"])
                if post - seen.get(key, -np.inf) < 3 * DAY:     # зеркало повторяет посты; тот же заголовок позже — новое закрытие
                    continue
                seen[key] = post; posts.append((c, e))
        by = {}
        for c, e in posts:
            by.setdefault(c, []).append(e)
        for c, E in by.items():
            E.sort(key=lambda e: e.get("post", e["t"]))
            op = None
            for e in E:
                if e["kind"] == "start":
                    if op is not None and e["post"] - op["post"] > 30 * DAY:
                        rows.append(dict(ex=ex, coin=c, start=op["t"], end=np.nan, **{k: op[k] for k in ("typ", "tag", "sched", "title")}))
                        op = None
                    if op is None:
                        op = e
                elif op is not None:
                    if e["t"] >= op["t"]:
                        rows.append(dict(ex=ex, coin=c, start=op["t"], end=e["t"], **{k: op[k] for k in ("typ", "tag", "sched", "title")}))
                    op = None
            if op is not None:
                rows.append(dict(ex=ex, coin=c, start=op["t"], end=np.nan, **{k: op[k] for k in ("typ", "tag", "sched", "title")}))
    return pd.DataFrame(rows)


def premium(ex, coin, sym, mult, t_from, t_to):
    """Часы (время закрытия, с), премия монеты на бирже к фьючерсу и оборот за час в $; часы с оборотом < 10 тыс. $ — NaN."""
    x, u = KC[ex].get(coin), KC[ex].get("USDT")
    if x is None or u is None or sym not in ROW:
        return None
    m = (x["t"] + 3600 > t_from) & (x["t"] + 3600 <= t_to)
    tc = x["t"][m] + 3600
    iu = np.searchsorted(u["t"] + 3600, tc); iu2 = np.minimum(iu, len(u["t"]) - 1)
    rate = np.where((iu < len(u["t"])) & (u["t"][iu2] + 3600 == tc), u["c"][iu2].astype(float), np.nan)
    ig = np.searchsorted(G, tc); ig2 = np.minimum(ig, len(G) - 1)
    pb = np.where((ig < len(G)) & (G[ig2] == tc), CB[ROW[sym], ig2], np.nan)
    usd = x["v"][m].astype(float) / rate
    prem = x["c"][m].astype(float) * mult / rate / pb - 1
    prem = np.where(usd >= MIN_USD, prem, np.nan)
    return tc, prem, usd


def build():
    E = events()
    print(f"закрытий всего: {len(E)}; по биржам {E.ex.value_counts().to_dict()}; по типу {E.typ.value_counts().to_dict()}")
    E = E[(E.start >= T0) & (E.start <= T1) & (E.typ != "wd") & (E.tag != "warn")].copy()
    sy = [fut_of(c) for c in E.coin]
    E["s"] = [s for s, _ in sy]; E["mult"] = [m for _, m in sy]
    E = E[E.s.notna()].copy()
    E = E[[live(s)[0] <= t - DAY and live(s)[1] >= t for s, t in zip(E.s, E.start)]].copy()
    E["dur_h"] = (E.end - E.start) / 3600
    paths, pmax, first = [], [], {thr: [] for thr in (0.05, 0.10, 0.20)}
    pre = []
    for r in E.itertuples():
        stop = min(r.start + 7 * DAY, r.end) if np.isfinite(r.end) else r.start + 7 * DAY
        p = premium(r.ex, r.coin, r.s, r.mult, r.start - 7 * DAY, r.start + 21 * DAY)
        paths.append(p)
        if p is None:
            pmax.append(np.nan); pre.append(np.nan)
            for thr in first:
                first[thr].append(np.nan)
            continue
        tc, pr, _ = p
        inc = (tc > r.start) & (tc <= stop)
        pmax.append(np.nanmax(pr[inc]) if np.isfinite(pr[inc]).any() else np.nan)
        b = (tc > r.start - 7 * DAY) & (tc <= r.start)
        pre.append(np.nanmedian(pr[b]) if np.isfinite(pr[b]).any() else np.nan)
        for thr in first:
            k = np.flatnonzero(inc & (pr >= thr))
            first[thr].append(float(tc[k[0]]) if len(k) else np.nan)
    E["pre_med"] = pre; E["pmax"] = pmax
    for thr, v in first.items():
        E[f"t{int(thr * 100)}"] = v
    E["path"] = paths
    pickle.dump(E.reset_index(drop=True), open("s29/cages.pkl", "wb"))
    return E


if __name__ == "__main__":
    E = build()
    print(f"садков с фьючерсом Binance (10.2024–10.2026, без только вывода и предупреждений): {len(E)}")
    print("  по биржам:", E.ex.value_counts().to_dict(), "| тип:", E.typ.value_counts().to_dict(), "| причина:", E.tag.value_counts().to_dict())
    print(f"  с известным концом: {E.end.notna().sum()}; длительность, ч: медиана {E.dur_h.median():.0f}, "
          f"75% {E.dur_h.quantile(0.75):.0f}, 90% {E.dur_h.quantile(0.9):.0f}")
    print(f"  премия известна: {E.pmax.notna().sum()}; премия до закрытия (медиана 7 сут) — медиана {E.pre_med.median():+.3%}")
    for thr in (5, 10, 20):
        print(f"  премия в садке ≥ {thr}%: {E[f't{thr}'].notna().sum()}")
