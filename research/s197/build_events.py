"""s197 — таблица событий «расписанный выход» из кэша s196 (запись — s197/ВЫВОДЫ.md). Без цен после события и без доходов.

Одна строка — «держатель × сутки t_vis × источник». Столбцы:
- src, kind ('exit' — выход, 'ctl' — вход в блокировку той же формы; ctl только у ve, где такие события уже в кэше),
  sym (тикер перпа Binance), holder;
- t_vis — время, когда дневная сумма выходов держателя стала видна целиком (время последней части за сутки UTC);
  t_first — первая часть; t_x01 / t_x05 — время, когда накопленная за сутки сумма впервые достигла 0,1% / 0,5% обращения
  (NaN — не достигла); для ve t_vis — время события, которое установило конец блокировки T;
- T — когда монеты становятся ликвидными (по правилам сети на тот момент), T_exact, T_rule;
- amount (в монетах), f = amount / обращение CMC на сутки до t_vis, turn = стоимость (цена CMC закрытия последних полных
  суток до t_vis) к среднему суточному обороту перпа Binance за 7 полных суток до t_vis (NaN — нет данных);
- t_dec = max(t_vis, T − 7 сут) — момент, когда правило может сработать; f_dec, turn_dec — то же на t_dec;
- relocker — у ve: держатель с ≥ 2 прошлыми перезамками по истории до T − 7 сут (правило s196), lock_end — у ctl ve;
- special — строки снимка TIA 25.10.2024 (снимок выбран из-за разлока: смещение отбора, охват — отдельным ключом).
Хранятся строки с f ≥ 0,0005. Итог — /home/user/mc_data/s197/events.pkl, coverage.json, лог build_events.log.
Вспомогательные выгрузки (эры DOT/KSM, запросы Tezos, cooldown stkAAVE, эпохи GRT/LPT, смена срока TIA) — aux_fetch.py;
здесь же — эпохи EGLD и ROSE, время версий и цикл блокировки пулов Aptos (кэш /home/user/mc_data/s197/aux/)."""
import bisect
import calendar
import collections
import concurrent.futures as cf
import glob
import gzip
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s196/study")
from common196 import http, DAY, ts  # noqa: E402
from freq_lib import Circ  # noqa: E402
import evm_freq as EF  # noqa: E402

S196 = "/home/user/mc_data/s196"
OUT = "/home/user/mc_data/s197"
AUX = f"{OUT}/aux"
D = "/home/user/mc_data"
F_MIN = 0.0005
NOW = None                      # конец данных: задаётся по источникам


def tparse(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def dstart(t):
    return int(t // DAY * DAY)


def aux_json(name, fn=None):
    p = f"{AUX}/{name}.json"
    if os.path.exists(p):
        return json.load(open(p))
    if fn is None:
        return None
    v = fn()
    json.dump(v, open(p, "w"))
    return v


# ---------- обращение, цена, оборот (без заглядывания) ----------

CIRC, PX, TURN = {}, {}, {}


def circ_at(sym, t):
    if sym not in CIRC:
        CIRC[sym] = Circ(sym)
    return CIRC[sym].at(t)


def price_before(sym, t):
    """цена закрытия CMC последних полных суток до t (закрытие суток d известно в d + 1 00:00)."""
    if sym not in PX:
        p = f"{S196}/circ/{sym}.json"
        rows = json.load(open(p)) if os.path.exists(p) else []
        rows = sorted((ts(d_) + DAY, px) for d_, c_, px in rows if px)
        PX[sym] = ([a for a, _ in rows], [b for _, b in rows])
    xs, ys = PX[sym]
    i = bisect.bisect_right(xs, t) - 1
    return ys[i] if i >= 0 else None


PANELS = []


def _panel_series(sym):
    if not PANELS:
        for p in ("2020–2022", "2022–2024", "2024–2026"):
            PANELS.append(pd.read_pickle(f"{D}/s183/daily_{p}.pkl")[["d", "s", "qv"]])
    if sym not in TURN:
        ser = []
        for d in PANELS:
            g = d[d["s"].isin([sym, f"1000{sym}"])]
            if len(g):
                ser.append(g.groupby("d")["qv"].sum())
        TURN[sym] = pd.concat(ser).groupby(level=0).last().sort_index() if ser else pd.Series(dtype=float)
    return TURN[sym]


def turnover_before(sym, t):
    """средний суточный оборот перпа (панели s183, qv) за 7 полных суток до суток t; ≥ 3 суток с данными."""
    q = _panel_series(sym)
    if q.empty:
        return None
    d0 = dstart(t)
    w = q[(q.index >= d0 - 7 * DAY) & (q.index <= d0 - DAY)]
    w = w[w > 0]
    return float(w.mean()) if len(w) >= 3 else None


def measures(sym, amount, t):
    c = circ_at(sym, t)
    f = amount / c if c else np.nan
    px, tv = price_before(sym, t), turnover_before(sym, t)
    turn = amount * px / tv if (px and tv) else np.nan
    return f, turn


# ---------- сборка строк ----------

def group_exits(raw, src, sym):
    """raw: [(holder, t, T, T_exact, amount, T_rule)] → строки «держатель × сутки» (сумма, T — самое раннее)."""
    g = collections.defaultdict(list)
    for r in raw:
        g[(r[0], dstart(r[1]))].append(r)
    rows = []
    for (h, d0), parts in g.items():
        parts.sort(key=lambda x: x[1])
        amount = sum(p[4] for p in parts)
        t_vis = parts[-1][1]
        c = circ_at(sym, parts[0][1])
        if not c or amount / c < F_MIN * 0.9:
            continue
        cum, tx01, tx05 = 0.0, np.nan, np.nan
        for p in parts:
            cum += p[4]
            cc = circ_at(sym, p[1]) or c
            if math.isnan(tx01) and cum / cc >= 0.001:
                tx01 = p[1]
            if math.isnan(tx05) and cum / cc >= 0.005:
                tx05 = p[1]
        Ts = [p[2] for p in parts if p[2] is not None]
        T = min(Ts) if Ts else np.nan
        rows.append(dict(src=src, kind="exit", sym=sym, holder=str(h), t_vis=float(t_vis), t_first=float(parts[0][1]),
                         t_x01=tx01, t_x05=tx05, T=float(T) if Ts else np.nan,
                         T_exact=bool(Ts) and all(p[3] for p in parts),
                         T_rule=parts[0][5], amount=float(amount), n_parts=len(parts)))
    return rows


def finish(rows):
    out = []
    for r in rows:
        r["f"], r["turn"] = measures(r["sym"], r["amount"], r["t_vis"])
        T = r["T"]
        r["t_dec"] = float(max(r["t_vis"], T - 7 * DAY)) if not (isinstance(T, float) and math.isnan(T)) else r["t_vis"]
        r["f_dec"], r["turn_dec"] = measures(r["sym"], r["amount"], r["t_dec"])
        if r["f"] >= F_MIN or (r["src"] in VE and r.get("f_dec", 0) >= F_MIN):
            out.append(r)
    return out


VE = ("vecrv", "vependle", "vefxs", "veyfi")
COV = {}


# ---------- Cosmos SDK: архивные снимки s196 ----------

def cosmos():
    tia_ut = aux_json("tia_unbonding")            # 1 814 400 → 1 213 200 с на высоте 8 662 013 (24.11.2025)
    rows = []
    for ch, sym in (("atom", "ATOM"), ("tia", "TIA"), ("kava", "KAVA")):
        files = sorted(glob.glob(f"{S196}/cosmos/{ch}_*.json"))
        if ch == "tia":
            files += [f"{S196}/cosmos/special_tia_2024-10-25.json"]
        for p in files:
            s = json.load(open(p))
            special = os.path.basename(p).startswith("special")
            t_snap = s["time"]
            raw = []
            for dlg, val, ch_h, comp, init_b, bal in s["rows"]:
                if ch == "tia" and ch_h >= tia_ut["height"]:
                    ut = int(tia_ut["after"].rstrip("s"))
                else:
                    ut = 1814400
                T = tparse(comp)
                raw.append((dlg, T - ut, float(T), True, init_b / 1e6, f"completion_time; t_vis = T − {ut // 3600} ч"))
            ut_snap = int(tia_ut["after"].rstrip("s")) if (ch == "tia" and s["height"] >= tia_ut["height"]) else 1814400
            key = "tia_special" if special else ch
            COV.setdefault(key, []).append([float(t_snap - ut_snap), float(t_snap)])
            rr = group_exits(raw, ch, sym)
            for r in rr:
                r["special"] = special
            rows += rr
        print(f"{ch}: снимков {len(files)}, строк (до порога) {sum(1 for r in rows if r['src'] == ch)}", flush=True)
    return rows


# ---------- Polkadot, Kusama: Staking.Unbonded + границы эр ----------

def dot_ksm():
    rows = []
    for net, src, sym, sess in (("polkadot", "dot", "DOT", 4 * 3600), ("kusama", "ksm", "KSM", 3600)):
        eras = aux_json(f"eras_{net}")                # [эра, блок, время конца эры]
        start = {e + 1: t for e, b, t in eras}        # активная эра e+1 начинается в конце эры e
        e_sorted = sorted(start.items())
        es = [e for e, _ in e_sorted]
        tsr = [t for _, t in e_sorted]
        era_len = DAY if net == "polkadot" else DAY / 4

        def start_of(e):
            if e in start:
                return float(start[e])
            # за пределами известного — шагом длины эры от ближайшей известной
            i = bisect.bisect_left(es, e)
            i = min(max(i, 0), len(es) - 1)
            return float(tsr[i] + (e - es[i]) * era_len)

        ev = json.load(open(f"{S196}/{net}_unbonded.json"))
        t_lo = ts("2020-08-22") if net == "polkadot" else 0   # до редоминации DOT (21.08.2020) — старые единицы
        raw = []
        tmin, tmax = 1e12, 0
        for b, tms, stash, amt in ev:
            t = tms / 1000
            if t < t_lo or amt is None:
                continue
            tmin, tmax = min(tmin, t), max(tmax, t)
            i = bisect.bisect_right(tsr, t) - 1
            if i < 0:
                continue
            a = es[i]                                 # активная эра в момент t
            nxt = start_of(a + 1)
            ce = a + 1 if t >= nxt - sess else a      # current_era: +1 в последнюю сессию эры
            T = start_of(ce + 28) - sess              # current_era станет ≥ ce + 28 за сессию до активации эры
            raw.append((stash, t, T, True, amt, "эра +28 (current_era), границы эр — EraPaid/EraPayout"))
        COV[src] = [[float(tmin), float(tmax)]]
        rr = group_exits(raw, src, sym)
        rows += rr
        print(f"{src}: событий {len(raw)}, строк (до порога) {len(rr)}", flush=True)
    return rows


# ---------- MultiversX: unDelegate (выборка суток), T = начало эпохи (e + 10) ----------

def egld_epoch_start(e):
    cache = aux_json("egld_epochs") or {}
    return cache.get(str(e))


def egld_epochs(need):
    p = f"{AUX}/egld_epochs.json"
    cache = json.load(open(p)) if os.path.exists(p) else {}
    miss = [e for e in sorted(set(need)) if str(e) not in cache]

    def one(e):
        d = http(f"https://api.multiversx.com/blocks?shard=4294967295&size=1&epoch={e}&order=asc&fields=timestamp,epoch",
                 timeout=40, tries=3)
        return e, (d[0]["timestamp"] if d else None)
    with cf.ThreadPoolExecutor(4) as ex:
        for e, t in ex.map(one, miss):
            if t:
                cache[str(e)] = t
    json.dump(cache, open(p, "w"))
    return {int(k): v for k, v in cache.items()}


def egld():
    SYS = "erd1qqqqqqqqqqqqqqqpqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
    d = json.load(open(f"{S196}/egld_undelegate.json"))
    raw = []
    for k, txs in d.items():
        COV.setdefault("egld", []).append([float(int(k)), float(int(k) + DAY)])
        for t, snd, rcv, amt in txs:
            if rcv.startswith(SYS) and amt and amt < 5e7:
                raw.append((snd, float(t), None, False, amt, "начало эпохи (e + 10)"))
    rows = group_exits(raw, "egld", "EGLD")
    rows = [r for r in rows if (circ_at("EGLD", r["t_first"]) and r["amount"] / circ_at("EGLD", r["t_first"]) >= F_MIN * 0.9)]
    # эпоха t_vis: опорные эпохи через 50 → кусочно-линейная оценка → начала соседних эпох
    anc = egld_epochs(list(range(150, 2351, 50)))
    ak = sorted(anc)

    def est(t):
        i = max(0, min(bisect.bisect_right([anc[k] for k in ak], t) - 1, len(ak) - 2))
        e0, e1 = ak[i], ak[i + 1]
        return int(e0 + (t - anc[e0]) * (e1 - e0) / (anc[e1] - anc[e0]))
    need = []
    for r in rows:
        k = est(r["t_first"])
        need += list(range(k - 2, k + 3)) + list(range(k + 8, k + 13))
    st = egld_epochs(need)
    keys = sorted(st)
    for r in rows:
        Ts = []
        # T — самое раннее завершение в группе: по первой части (t_first) — её эпоха раньше или та же
        t = r["t_first"]
        i = bisect.bisect_right([st[k] for k in keys], t) - 1
        if i >= 0:
            e = keys[i]
            if (e + 10) in st:
                Ts.append(st[e + 10])
        r["T"] = float(Ts[0]) if Ts else np.nan
        r["T_exact"] = bool(Ts)
    print(f"egld: суток в выборке {len(d)}, строк (до порога) {len(rows)}, эпох в кэше {len(st)}", flush=True)
    return rows


# ---------- Oasis: ReclaimEscrow (выборка суток), T = начало эпохи debond_end_time ----------

def rose():
    d = json.load(open(f"{S196}/rose_reclaim.json"))
    ex = json.load(open(f"{S196}/rose_exact.json"))
    raw = []
    for k, txs in d.items():
        COV.setdefault("rose", []).append([float(int(k)), float(int(k) + DAY)])
        for tstr, snd, acc, shares, h in txs:
            t = tparse(tstr)
            raw.append((snd, float(t), h, False, shares, "начало эпохи debond_end_time"))
    # предварительная группировка по долям (сумма ≤ доли × 1,45) → кандидаты → точные суммы и эпохи по tx_hash
    g = collections.defaultdict(list)
    for r in raw:
        g[(r[0], dstart(r[1]))].append(r)
    need = []
    for key, parts in g.items():
        c = circ_at("ROSE", parts[0][1])
        if c and sum(p[4] for p in parts) * 1.45 / c >= F_MIN:
            need += [p[2] for p in parts if p[2] not in ex]
    for h in need:
        q = http(f"https://nexus.oasis.io/v1/consensus/events?tx_hash={h}&type=staking.escrow.debonding_start", timeout=60)
        evb = (((q or {}).get("events") or [{}])[0]).get("body") or {}
        ex[h] = [int(evb.get("amount") or 0) / 1e9, evb.get("debond_end_time")]
        time.sleep(0.1)
    json.dump(ex, open(f"{AUX}/rose_exact_plus.json", "w"))
    # эпоха → время (Nexus: эпоха → start_height → время блока); будущие — экстраполяция
    ep_cache_p = f"{AUX}/rose_epochs.json"
    ep = json.load(open(ep_cache_p)) if os.path.exists(ep_cache_p) else {}
    want = set()
    for key, parts in g.items():
        c = circ_at("ROSE", parts[0][1])
        if c and sum(p[4] for p in parts) * 1.45 / c >= F_MIN:
            for p in parts:
                e = (ex.get(p[2]) or [0, None])[1]
                if e:
                    want.add(int(e))
    for e in sorted(want):
        if str(e) in ep:
            continue
        q = http(f"https://nexus.oasis.io/v1/consensus/epochs/{e}", timeout=60, tries=2)
        if q and q.get("start_height"):
            b = http(f"https://nexus.oasis.io/v1/consensus/blocks/{q['start_height']}", timeout=60, tries=2)
            if b and b.get("timestamp"):
                ep[str(e)] = [tparse(b["timestamp"]), True]
        time.sleep(0.1)
    # экстраполяция для будущих эпох по двум последним известным
    known = sorted((int(k), v[0]) for k, v in ep.items() if v[1])
    if len(known) >= 2:
        (ea, ta), (eb, tb) = known[0], known[-1]
        per = (tb - ta) / max(1, eb - ea)
        for e in want:
            if str(e) not in ep:
                ep[str(e)] = [tb + (e - eb) * per, False]
    json.dump(ep, open(ep_cache_p, "w"))
    raw2 = []
    for snd, t, h, _, shares, rule in raw:
        amt, e = (ex.get(h) or [None, None])
        if amt:
            T, exact = (ep.get(str(int(e))) or [None, False]) if e else (None, False)
            raw2.append((snd, t, T, bool(exact), amt, rule))
        else:
            raw2.append((snd, t, None, False, shares, rule + " (сумма — доли, нижняя оценка)"))
    rows = group_exits(raw2, "rose", "ROSE")
    print(f"rose: суток {len(d)}, догружено точных {len(need)}, эпох {len(want)}, строк (до порога) {len(rows)}", flush=True)
    return rows


# ---------- Tezos: unstake (ручной, не автостейкинг), T = unlockTime запроса TzKT ----------

def xtz():
    def fetch():
        out, last = [], 0
        while True:
            d = http("https://api.tzkt.io/v1/staking/updates?type=unstake&limit=10000&sort.asc=id"
                     f"&id.gt={last}&select=id,timestamp,cycle,amount,staker.address,baker.address,stakingOpId,"
                     "autostakingOpId,delegationOpId")
            if not d:
                break
            out += d
            last = d[-1]["id"]
            if len(d) < 10000:
                break
        return out
    upd = aux_json("tezos_unstake_full", fetch)
    req = aux_json("tezos_requests")
    unlock = {(r["staker.address"], r["baker.address"], r["cycle"]): tparse(r["unlockTime"]) for r in req if r.get("unlockTime")}
    raw, n_auto = [], 0
    tmin, tmax = 1e12, 0
    for u in upd:
        t = tparse(u["timestamp"])
        tmin, tmax = min(tmin, t), max(tmax, t)
        if u.get("autostakingOpId"):
            n_auto += 1
            continue
        T = unlock.get((u["staker.address"], u["baker.address"], u["cycle"]))
        raw.append((u["staker.address"], float(t), float(T) if T else None, T is not None, u["amount"] / 1e6,
                    "unlockTime запроса (TzKT)"))
    COV["xtz"] = [[float(tmin), float(tmax)]]
    rows = group_exits(raw, "xtz", "XTZ")
    print(f"xtz: unstake {len(upd)} (автостейкинг пропущен: {n_auto}), строк (до порога) {len(rows)}", flush=True)
    return rows


# ---------- Aptos: UnlockStake(Event) пулов делегирования, T = locked_until_secs пула на версии ----------

def apt():
    d = json.load(open(f"{S196}/aptos_unlock.json"))
    seen, ev = set(), []
    for v, amt, dl, pool in d["rows"]:
        key = (v, dl, pool, round(amt, 8))           # v1 и v2-события одного действия — один раз
        if key not in seen:
            seen.add(key)
            ev.append((v, amt, dl, pool))
    vt = sorted((int(x[0]), tparse(x[1])) for x in d["vt"].values())
    xs = [a for a, _ in vt]

    def vtime(v):
        i = max(0, min(bisect.bisect_right(xs, v) - 1, len(vt) - 2))
        (v0, t0), (v1, t1) = vt[i], vt[i + 1]
        return t0 + (t1 - t0) * (v - v0) / max(1, v1 - v0)
    # кандидаты по приблизительному времени, затем точное время версии и цикл блокировки пула (архивный REST)
    cand = [e for e in ev if circ_at("APT", vtime(e[0])) and e[1] / circ_at("APT", vtime(e[0])) >= F_MIN * 0.5]
    p = f"{AUX}/aptos_exact.json"
    cache = json.load(open(p)) if os.path.exists(p) else {}
    A = "https://archive.mainnet.aptoslabs.com/v1"

    def one(e):
        v, amt, dl, pool = e
        k = f"{v}:{pool}"
        if k in cache:
            return k, cache[k]
        tx = http(f"{A}/transactions/by_version/{v}", timeout=60, tries=3)
        sp = http(f"{A}/accounts/{pool}/resource/0x1::stake::StakePool?ledger_version={v}", timeout=60, tries=3)
        t = int(tx["timestamp"]) / 1e6 if tx and tx.get("timestamp") else None
        lu = int(sp["data"]["locked_until_secs"]) if sp and sp.get("data") else None
        return k, [t, lu]
    with cf.ThreadPoolExecutor(4) as exq:
        for k, val in exq.map(one, cand):
            cache[k] = val
    json.dump(cache, open(p, "w"))
    raw = []
    for v, amt, dl, pool in cand:
        t, lu = cache.get(f"{v}:{pool}") or [None, None]
        exact_t = t is not None
        t = t if exact_t else vtime(v)
        if lu is not None and lu < t:
            # блокировка пула уже истекла (пул вне набора валидаторов или не продлён): ожидающее выходит со сменой
            # эпохи (≤ 2 ч) — T = t_vis
            raw.append((dl, float(t), float(t), exact_t, amt, "locked_until_secs < t_vis → T = t_vis (смена эпохи ≤ 2 ч)"))
            continue
        raw.append((dl, float(t), float(lu) if lu else None, lu is not None and exact_t, amt,
                    "locked_until_secs пула на версии (архивный REST)"))
    tlast = vtime(max(e[0] for e in ev))
    COV["apt"] = [[float(ts("2023-02-14")), float(tlast)]]
    rows = group_exits(raw, "apt", "APT")
    print(f"apt: событий {len(ev)} (после снятия двойных v1/v2), кандидатов {len(cand)}, строк (до порога) {len(rows)}", flush=True)
    return rows


# ---------- Ethereum: stkAAVE, API3, GRT L1, LPT L1 ----------

def evm_simple():
    cd = aux_json("aave_cooldown")["changes"]          # [блок, было, стало]
    cool = [(0, 10 * DAY)] + [(b, after) for b, before, after in cd]
    rows = []
    # stkAAVE Cooldown(user, amount)
    raw, tmin, tmax = [], 1e12, 0
    for b, tx, tp, data in EF.load("stkaave"):
        t = EF.btime(b)
        tmax = max(tmax, t)
        w = EF.words(data)
        if not w:
            continue
        tmin = min(tmin, t)
        c = [s for blk, s in cool if blk <= b][-1]
        raw.append((EF.addr(tp[1]), float(t), float(t + c), True, w[0] / 1e18, "t + действующий COOLDOWN_SECONDS (смены по блокам)"))
    COV["stkaave"] = [[float(tmin), float(tmax)]]
    rows += group_exits(raw, "stkaave", "AAVE")
    # API3 ScheduledUnstake(user, amount, shares, scheduledFor, userShares)
    raw, tmin, tmax = [], 1e12, 0
    for b, tx, tp, data in EF.load("api3"):
        t = EF.btime(b)
        tmin, tmax = min(tmin, t), max(tmax, t)
        w = EF.words(data)
        raw.append((EF.addr(tp[1]), float(t), float(w[2]), True, w[0] / 1e18, "scheduledFor"))
    COV["api3"] = [[float(tmin), float(tmax)]]
    rows += group_exits(raw, "api3", "API3")
    # GRT L1 StakeDelegatedLocked(indexer, delegator, shares, tokens, until): начало эпохи until
    def grt_start(e):
        return 11446768 + e * 6646 if e < 776 else 16604064 + (e - 776) * 7200
    raw, tmin, tmax = [], 1e12, 0
    for b, tx, tp, data in EF.load("grt_l1"):
        t = EF.btime(b)
        tmin, tmax = min(tmin, t), max(tmax, t)
        w = EF.words(data)
        raw.append((EF.addr(tp[2]), float(t), float(EF.btime(grt_start(w[2]))), True, w[1] / 1e18,
                    "начало эпохи until (EpochManager: 6646 бл., с эпохи 776 — 7200)"))
    # L1 видит все выходы только до переезда делегаций на Arbitrum (L2 Transfer Tools — середина 2023 г.):
    # охват обрезан 01.06.2023, строки L1 после этой даты в таблице остаются (только часть выходов)
    COV["grt_l1"] = [[float(tmin), float(min(tmax, ts("2023-06-01")))]]
    rows += group_exits(raw, "grt_l1", "GRT")
    # LPT L1 Unbond(delegate, delegator, lockId, amount, withdrawRound): начало раунда
    raw, tmin, tmax = [], 1e12, 0
    for b, tx, tp, data in EF.load("lpt_l1"):
        t = EF.btime(b)
        tmin, tmax = min(tmin, t), max(tmax, t)
        w = EF.words(data)
        raw.append((EF.addr(tp[2]), float(t), float(EF.btime(5529600 + (w[2] - 960) * 5760)), True, w[1] / 1e18,
                    "начало раунда withdrawRound (RoundsManager: 5760 бл.)"))
    COV["lpt_l1"] = [[float(tmin), float(tmax)]]
    rows += group_exits(raw, "lpt_l1", "LPT")
    print("evm: stkaave / api3 / grt_l1 / lpt_l1 строк (до порога):",
          [sum(1 for r in rows if r["src"] == s) for s in ("stkaave", "api3", "grt_l1", "lpt_l1")], flush=True)
    return rows


# ---------- ve: концы блокировок «на T − 7 сут ещё в T» и входы той же формы ----------

def ve_rows(name, sym, data_end):
    ev = EF.ve_events(name)                       # [(t, kind add|set|wd, holder, amount, end)]
    st = {}                                       # holder → [amount, end, end_set_time]
    relock = collections.Counter()
    last_wd = {}
    checks = []                                   # (время проверки T − 7, holder, T)
    seen_pairs = set()
    for t, k, h, a, e in ev:
        if k in ("add", "set") and e and (h, e) not in seen_pairs:
            seen_pairs.add((h, e))
            if e - 7 * DAY <= data_end:
                checks.append((e - 7 * DAY, h, e))
    checks.sort()
    exits, ctl = [], []
    i = 0
    for chk, h, E in checks + [(float("inf"), None, None)]:
        while i < len(ev) and ev[i][0] < chk:
            t, k, hh, a, e = ev[i]
            prev = st.get(hh, [0.0, 0, None])
            if k in ("add", "set"):
                if (prev[0] > 0 and prev[1] and prev[1] <= t + DAY) or (hh in last_wd and t - last_wd[hh] <= 14 * DAY):
                    relock[hh] += 1
                if k == "add":
                    new_amt = prev[0] + a
                    new_end = max(prev[1], e)
                    added = a
                else:
                    new_amt, new_end = a, e
                    added = a - prev[0] if prev[1] and prev[0] else a
                end_set = prev[2] if (new_end == prev[1] and prev[2] is not None and prev[0] > 0) else t
                st[hh] = [new_amt, new_end, end_set]
                if added > 0:
                    ctl.append((hh, float(t), float(t + 7 * DAY), False, added, f"ctl: вход в блокировку; T = t + 7 сут",
                                float(new_end), relock[hh] >= 2))
            else:
                last_wd[hh] = t
                st[hh] = [0.0, 0, None]
            i += 1
        if h is None:
            break
        s = st.get(h)
        if s and s[0] > 0 and s[1] == E:
            exits.append((h, float(s[2]), float(E), True, s[0], "конец ve-блокировки (на T − 7 сут ещё в T)",
                          relock[h] >= 2))
    rows = []
    for x in exits:                               # одна строка на (держатель, конец)
        rows.append(dict(src=name, kind="exit", sym=sym, holder=x[0], t_vis=x[1], t_first=x[1], t_x01=np.nan,
                         t_x05=np.nan, T=x[2], T_exact=True, T_rule=x[5], amount=float(x[4]), n_parts=1,
                         relocker=bool(x[6])))
    # ctl: сумма за сутки по держателю
    g = collections.defaultdict(list)
    for x in ctl:
        g[(x[0], dstart(x[1]))].append(x)
    for (h, d0), parts in g.items():
        parts.sort(key=lambda p: p[1])
        rows.append(dict(src=name, kind="ctl", sym=sym, holder=h, t_vis=parts[-1][1], t_first=parts[0][1],
                         t_x01=np.nan, t_x05=np.nan, T=parts[-1][1] + 7 * DAY, T_exact=False, T_rule=parts[0][5],
                         amount=float(sum(p[4] for p in parts)), n_parts=len(parts),
                         lock_end=parts[-1][6], relocker=bool(parts[-1][7])))
    starts = [e[0] for e in ev]
    COV[name] = [[float(min(starts)), float(data_end)]]       # для ve — по t_dec (= T − 7 сут), см. отчёт
    print(f"{name}: концов (на T − 7) {len(exits)}, входов-ctl (по суткам) {len(g)}", flush=True)
    return rows


def main():
    os.makedirs(AUX, exist_ok=True)
    rows = []
    rows += cosmos()
    rows += dot_ksm()
    rows += egld()
    rows += rose()
    rows += xtz()
    rows += apt()
    rows += evm_simple()
    data_end_eth = max(EF.btime(b) for b, *_ in EF.load("vecrv"))
    for name, sym in (("vecrv", "CRV"), ("vependle", "PENDLE"), ("vefxs", "FXS"), ("veyfi", "YFI")):
        rows += ve_rows(name, sym, data_end_eth)
    rows = finish(rows)
    df = pd.DataFrame(rows)
    for c in ("relocker", "special"):
        if c not in df:
            df[c] = np.nan
    if "lock_end" not in df:
        df["lock_end"] = np.nan
    df["T_exact"] = df["T_exact"].astype(bool)
    for c in ("relocker", "special"):
        df[c] = df[c].map(lambda x: pd.NA if (x is None or (isinstance(x, float) and math.isnan(x))) else bool(x)).astype("boolean")
    cols = ["src", "kind", "sym", "holder", "t_vis", "t_first", "t_x01", "t_x05", "T", "T_exact", "T_rule", "amount",
            "f", "turn", "t_dec", "f_dec", "turn_dec", "relocker", "lock_end", "special", "n_parts"]
    df = df[cols].sort_values(["src", "t_vis"]).reset_index(drop=True)
    df.to_pickle(f"{OUT}/events.pkl")
    json.dump(COV, open(f"{OUT}/coverage.json", "w"))
    print("строк всего", len(df), "из них exit", int((df["kind"] == "exit").sum()), flush=True)
    report(df)


def report(df):
    per = [("2020–2022", ts("2020-10-01"), ts("2022-10-01")), ("2022–2024", ts("2022-10-01"), ts("2024-10-01")),
           ("2024–2026", ts("2024-10-01"), ts("2026-10-19"))]
    print("\nexit-строк по src × периоду (по t_vis), ≥ 0,1% / ≥ 0,5% обращения; у ve период — по t_dec (T − 7)")
    print(f"{'src':10s} | " + " | ".join(f"{p:^17s}" for p, _, _ in per) + " | T точный, %")
    for src, g in df[df["kind"] == "exit"].groupby("src"):
        cells = []
        tcol = g["t_dec"] if src in VE else g["t_vis"]
        for p, a, b in per:
            m = (tcol >= a) & (tcol < b)
            cells.append(f"{int(((g['f'] >= 0.001) & m).sum()):7d} {int(((g['f'] >= 0.005) & m).sum()):7d}")
        print(f"{src:10s} | " + " | ".join(cells) + f" | {100 * g['T_exact'].mean():5.1f}")
    ctl = df[df["kind"] == "ctl"]
    if len(ctl):
        print("ctl-строк (ve, ≥ 0,1% / ≥ 0,5%):", {s: (int((g["f"] >= 0.001).sum()), int((g["f"] >= 0.005).sum()))
                                                  for s, g in ctl.groupby("src")})
    e = df[df["kind"] == "exit"]
    lag = (e["T"] - e["t_vis"]) / DAY
    print("\nT − t_vis, сут (медиана, p10, p90) по src:")
    for src, g in e.groupby("src"):
        l = ((g["T"] - g["t_vis"]) / DAY).dropna()
        if len(l):
            print(f"  {src:10s} {l.median():7.1f} {l.quantile(0.1):7.1f} {l.quantile(0.9):7.1f}  нет T: {int(g['T'].isna().sum())}")


if __name__ == "__main__":
    main()
