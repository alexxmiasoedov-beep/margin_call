"""s181 — история собственных токенов казначейств DefiLlama (api.llama.fi/treasury/<slug>, кэш treasury_fetch.py):
охват по периодам и частота событий «собственные токены казначейства упали на ≥ 0,5% / ≥ 1% монет в обращении за 7 сут».

Сопоставление с перпом Binance USDT-M: тикер протокола (или крупнейший собственный токен у DAO без тикера) = база перпа;
ложные совпадения отброшены по id CoinGecko (s160/perp_map.json) и вручную (FALSE). Монеты в обращении и оборот — CMC
data-api (cmc_hist.py). Флаги: возврат (за 14 сут вернулось ≥ 80% падения), ступенька (≥ 90% падения за одни сутки),
разлок той же монеты ≥ 1% (DefiLlama emissions, s139/unlock_test.events) в [−10; +3] сут, завод 🐋 (s160_events.pkl:
Binance, ≥ 0,5% обращения) в [−7; +3] сут. Только частоты и размеры: доходы и цены после событий не считаются.
Запуск: python3 -I treasury_events.py"""
import json
import os
import warnings
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import cmc_hist as H  # noqa: E402

DAY = 86400
warnings.filterwarnings("ignore", category=RuntimeWarning)
FALSE = {"hyperblast": "HYPE — HyperBlast, перп HYPE — Hyperliquid",
         "metronome": "MET — Metronome, перп MET — Meteora",
         "the-standard": "TST — The Standard, перп TST — мем BNB Chain",
         "nullmask": "MASK — Nullmask, перп MASK — Mask Network",
         "bankless": "BANK — Bankless DAO, перп BANK — Lorenzo",
         "furucombo": "COMBO — Furucombo, перп COMBO — бывший Cocos-BCX",
         "parallel-protocol": "PRL — Parallel (MIMO), перп PRL — Perle"}
EXTRA = {"flokifi-locker": ["TOKEN"]}          # второй собственный токен экосистемы с перпом
ONLY = {"frax-finance": ["FXS"]}               # FRAX в истории — стейблкоин до переименования 2025 г.
NOTSYM = {"USDC", "USDT", "DAI", "WETH", "ETH", "WBTC", "BTC", "USDE", "FRAX", "SAFE", "PENDLE", "MORPHO"}


def series():
    P = C.perps()
    B = {}
    for k in P:
        B.setdefault(C.base(k).upper(), []).append(k)
    pm = {x["perp"]: x for x in json.load(open(f"{C.D}/s160/perp_map.json"))}
    cand = {x["slug"]: x for x in json.load(open(f"{C.OUT}/treasury_candidates.json"))}
    cmap = H.cmc_map()
    out, rej = [], []
    for slug, x in sorted(cand.items()):
        fn = f"{C.OUT}/treasury/{slug}.json.gz"
        if not os.path.exists(fn):
            continue
        d = C.jload(fn)
        o = ((d.get("chainTvls") or {}).get("OwnTokens") or {}).get("tokens") or []
        if not o:
            continue
        mx = {}
        for r in o:
            for k, v in r["tokens"].items():
                mx[k] = max(mx.get(k, 0), v or 0)
        sym = (x.get("sym") or "-").upper()
        if slug in ONLY:
            own = ONLY[slug]
        elif sym in B and sym in {k.upper() for k in mx}:
            own = [k for k in mx if k.upper() == sym] + EXTRA.get(slug, [])
        elif sym in ("-", ""):
            c = [k for k in mx if k.upper() in B and k.upper() not in NOTSYM]
            own = sorted(c, key=lambda k: -mx[k])[:1]
        else:
            own = []
        if not own:
            continue
        if slug in FALSE:
            rej.append((slug, FALSE[slug]))
            continue
        for s in own:
            perp = sorted(B[s.upper()], key=len)[0]
            g = (pm.get(perp) or {}).get("id")
            if g and d.get("gecko_id") and s.upper() == sym and g != d.get("gecko_id"):
                rej.append((slug, f"{s}: CoinGecko {d.get('gecko_id')} ≠ перп {g}"))
                continue
            cid = d.get("cmcId") if s.upper() == sym and d.get("cmcId") else None
            if not cid:
                cc = cmap.get(s.upper()) or []
                cid = cc[0][1] if cc else None
            t = np.array([r["date"] for r in o], float)
            h = np.array([float(r["tokens"].get(s, 0.0) or 0.0) for r in o])
            other = np.array([sum(float(v or 0) for k, v in r["tokens"].items() if k != s) for r in o])
            out.append(dict(slug=slug, sym=s.upper(), perp=perp, cmc=int(cid) if cid else None, t=t, h=h, other=other,
                            spans=P[perp]))
    return out, rej


def daily(s):
    """Сутки UTC → последнее значение за сутки, пропуски до 3 сут заполняются вперёд."""
    day = (s["t"] // DAY).astype(int)
    df = pd.DataFrame({"day": day, "h": s["h"], "o": s["other"]}).groupby("day").last()
    idx = np.arange(df.index.min(), df.index.max() + 1)
    df = df.reindex(idx).ffill(limit=3)
    return df


def circ_frame(cid):
    L = H.hist(cid)
    if not L:
        return None
    df = pd.DataFrame(L, columns=["date", "circ", "vol", "px"])
    df["day"] = ((pd.to_datetime(df.date) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1D")).astype(int)
    return df.groupby("day").last()


def main():
    S, rej = series()
    print("отброшены ложные совпадения:")
    for r in rej:
        print("  ", r[0], "—", r[1])
    print(f"рядов «казначейство — собственный токен с перпом»: {len(S)}; протоколов {len({s['slug'] for s in S})}; "
          f"перпов {len({s['perp'] for s in S})}")
    UNL = None
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "s139"))
        import unlock_test as U  # noqa: E402
        UNL = U.events()
        UNL = UNL[UNL.share.notna()]
        UNL["day"] = UNL["T"] // DAY
        UNL = UNL.groupby(["key", "day"]).share.sum().reset_index()
        UNL = UNL[UNL.share >= 0.01]
    except Exception as e:
        print("разлоки не загружены:", e)
    W = pd.read_pickle(f"{C.D}/s160_events.pkl")
    W = W[(W.exch == "Binance") & (W.frac >= 0.005)]
    W["day"] = W.t // DAY
    rows, cover = [], []
    per_days = {p: (int(pd.Timestamp(a, tz="UTC").timestamp()) // DAY, int(pd.Timestamp(b, tz="UTC").timestamp()) // DAY)
                for p, (a, b) in C.PER.items()}
    for s in S:
        df = daily(s)
        cf = circ_frame(s["cmc"]) if s["cmc"] else None
        if cf is None or not len(cf):
            print("  нет обращения CMC:", s["slug"], s["sym"])
            continue
        df = df.join(cf[["circ", "vol", "px"]], how="left")
        df["circ"] = df["circ"].where(df["circ"] > 0).ffill(limit=7)
        for p, (a, b) in per_days.items():
            m = (df.index >= a) & (df.index < b) & df.h.notna()
            alive_days = sum(1 for dd in range(a, b, 7) if C.alive(s["spans"], dd * DAY))
            cover.append(dict(slug=s["slug"], sym=s["sym"], per=p, days=int(m.sum()), frac=m.sum() / (b - a),
                              perp_alive=alive_days > 0, hc=float(np.nanmedian((df.h / df.circ)[m])) if m.sum() else np.nan,
                              days_adv=float(np.nanmedian((df.h * df.px / (0.1 * df.vol.rolling(30, 5).median()))[m]))
                              if m.sum() else np.nan))
        h = df.h.values
        circ = df.circ.values
        days = df.index.values
        for thr in (0.005, 0.01):
            last = -10 ** 9
            for i in range(7, len(df)):
                if np.isnan(h[i]) or np.isnan(h[i - 7]) or not circ[i] or np.isnan(circ[i]):
                    continue
                d7 = h[i] - h[i - 7]
                if d7 > -thr * circ[i] or days[i] - last < 7:
                    continue
                last = days[i]
                t_ev = int(days[i]) * DAY
                drop = -d7
                fut = h[i + 1:i + 15]
                rev = bool(len(fut) and np.nanmax(fut) >= h[i] + 0.8 * drop)
                steps = np.diff(h[i - 7:i + 1])
                step = bool(np.nanmin(steps) <= -0.9 * drop)
                oth = df.o.values[i] - df.o.values[i - 7]
                adv = np.nanmedian(df.vol.values[max(0, i - 30):i]) if i > 5 else np.nan
                unl = bool(UNL is not None and len(UNL[(UNL.key == s["perp"]) & (UNL.day >= days[i] - 10) & (UNL.day <= days[i] + 3)]))
                wd = bool(len(W[(W.perp == s["perp"]) & (W.day >= days[i] - 7) & (W.day <= days[i] + 3)]))
                rows.append(dict(slug=s["slug"], sym=s["sym"], perp=s["perp"], thr=thr, t=t_ev, day=int(days[i]),
                                 frac=drop / circ[i], h_before=h[i - 7], drop=drop, usd=drop * df.px.values[i],
                                 adv=adv, to_adv=drop * df.px.values[i] / adv if adv and adv > 0 else np.nan,
                                 share_of_tr=drop / h[i - 7] if h[i - 7] > 0 else np.nan, revert=rev, step=step,
                                 other_up=oth > 0.8 * drop * (1 if s["sym"] else 1), zero=h[i] < 0.01 * h[i - 7],
                                 unlock=unl, whale=wd, alive=C.alive(s["spans"], t_ev)))
    E = pd.DataFrame(rows)
    E.to_pickle(f"{C.OUT}/treasury_events.pkl")
    CV = pd.DataFrame(cover)
    CV.to_pickle(f"{C.OUT}/treasury_cover.pkl")
    print("\nОхват (ряды с собственным токеном-перпом; в скобках — ряды с перпом, живым в периоде):")
    for p in C.PER:
        c = CV[CV.per == p]
        any_ = c[c.days > 0]; half = c[c.frac >= 0.5]
        print(f"  {p}: есть хоть день — {len(any_)} ({int(any_.perp_alive.sum())}); ≥ половины периода — {len(half)} "
              f"({int(half.perp_alive.sum())}); медиана запаса H/C {np.nanmedian(any_.hc):.1%}; "
              f"медиана дней продажи запаса при 10% оборота {np.nanmedian(any_.days_adv):.0f}")
    print("\nСобытий в месяц (перп жив; одно на перп за 7 сут):")
    for thr in (0.005, 0.01):
        x = E[(E.thr == thr) & E.alive].sort_values("t")
        keep, last = [], {}
        for r in x.itertuples():
            if r.t - last.get(r.perp, -10 ** 12) >= 7 * DAY:
                keep.append(r.Index); last[r.perp] = r.t
        x = x.loc[keep]
        for lab, y in (("все", x), ("без возврата", x[~x.revert]), ("без возврата и обнуления", x[~x.revert & ~x.zero]),
                       ("без возврата, без разлока", x[~x.revert & ~x.unlock]),
                       ("без возврата, без разлока, без 🐋", x[~x.revert & ~x.unlock & ~x.whale])):
            fr = [C.month_counts(y.t, p) for p in C.PER]
            print(f"  ≥ {thr:.1%} {lab:34s} " + " / ".join(f"{v:5.2f}" for v in fr) + f"   (всего {len(y)})")
        y = x[~x.revert]
        if len(y):
            print(f"     размеры (без возврата): медиана {y.frac.median():.2%} обращения, {y.usd.median() / 1e6:.2f} млн $, "
                  f"{y.to_adv.median():.2f} суточного оборота; доля запаса {y.share_of_tr.median():.1%}; "
                  f"ступенька {y.step.mean():.0%}; рост других собственных токенов {y.other_up.mean():.0%}; "
                  f"с разлоком {y.unlock.mean():.0%}; с 🐋 {y.whale.mean():.0%}")
            print("     по протоколам:", y.groupby("slug").size().sort_values(ascending=False).head(15).to_dict())


if __name__ == "__main__":
    main()
