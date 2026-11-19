"""s196 — цепочка «выход из блокировки → завод на биржу» для ERC-20 (без цен): крупные выходы (≥ 0,1% обращения) из
evm_freq (концы ve-блокировок без перезамка в истории, API3 ScheduledUnstake, stkAAVE Cooldown, GRT/LPT L1) — был ли
перевод того же адреса на адрес биржи (сбор s160: все переводы ≥ 0,05% обращения на 5331 адрес бирж, 10.2020–11.2026)
в [T − 1; T + 14] сут, где T — дата ликвидности; для сравнения — тот же адрес в [T − 60; T − 30] (до события)."""
import collections
import glob
import gzip
import json
from common196 import OUT, DAY, D
import evm_freq as EF
from freq_lib import fmt_t

TOK = {"CRV": "0xd533a949740bb3306d119cc777fa900ba034cd52", "PENDLE": "0x808507121b80c02388fad14726482e061b8da827",
       "FXS": "0x3432b6a60d23ca0dfca7761b7ab56459d9c964d0", "YFI": "0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e",
       "AAVE": "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9", "API3": "0x0b38210ea11411557c13457d4da7dc6ea731b88a",
       "GRT": "0xc944e90c64b2c07662a292be6244bdf05cda44a7", "LPT": "0x58b6a8a3302369daec383334672404ee733ab239"}


def deposits():
    want = set(TOK.values())
    dep = collections.defaultdict(list)          # (токен, отправитель) → [время]
    for p in sorted(glob.glob(f"{D}/s160/raw/b*.json.gz")):
        for b, tok, frm, to, amt, tx, li in json.load(gzip.open(p, "rt")):
            if tok in want:
                dep[(tok, frm)].append(EF.btime(b))
    return dep


def exits():
    import io, contextlib
    ev = []
    for name, sym, start in (("vecrv", "CRV", "2020-10-01"), ("vependle", "PENDLE", "2022-12-01"),
                             ("vefxs", "FXS", "2021-03-01"), ("veyfi", "YFI", "2023-04-01")):
        with contextlib.redirect_stdout(io.StringIO()):
            H = EF.ve_calendar(name, sym, start)
        ev += [(sym, h, W, f) for chk, f, h, W in H if f >= 0.001]
    for name, sym, lag in (("api3", "API3", 7), ("stkaave", "AAVE", 20), ("grt_l1", "GRT", 26), ("lpt_l1", "LPT", 7)):
        circ = EF.Circ(sym)
        for b, tx, tp, data in EF.load(name):
            w = EF.words(data)
            if name == "api3":
                a, h, T = w[0] / 1e18, EF.addr(tp[1]), w[2]
            elif name == "stkaave":
                if not w:
                    continue
                a, h, T = w[0] / 1e18, EF.addr(tp[1]), EF.btime(b) + lag * DAY
            else:
                a, h, T = w[1] / 1e18, EF.addr(tp[2]), EF.btime(b) + lag * DAY
            c = circ.at(EF.btime(b))
            if c and a / c >= 0.001:
                ev.append((sym, h, T, a / c))
    return ev


def main():
    dep = deposits()
    ev = exits()
    res = collections.defaultdict(lambda: [0, 0, 0])
    for sym, h, T, f in ev:
        ts_ = dep.get((TOK[sym], h), [])
        after = any(T - DAY <= t <= T + 14 * DAY for t in ts_)
        before = any(T - 60 * DAY <= t <= T - 30 * DAY for t in ts_)
        g = res[sym]
        g[0] += 1; g[1] += after; g[2] += before
    print("Крупные выходы (≥ 0,1% обращения) → перевод того же адреса на биржу (≥ 0,05% обращения, сбор s160)")
    print("монета | выходов | завод в [T−1; T+14] | завод в [T−60; T−30] (база)")
    tot = [0, 0, 0]
    for sym, g in sorted(res.items()):
        print(f"  {sym:6s} | {g[0]:4d} | {g[1]:4d} ({100 * g[1] / g[0]:.0f}%) | {g[2]:4d} ({100 * g[2] / g[0]:.0f}%)")
        tot = [a + b for a, b in zip(tot, g)]
    print(f"  ВСЕ    | {tot[0]:4d} | {tot[1]:4d} ({100 * tot[1] / tot[0]:.0f}%) | {tot[2]:4d} ({100 * tot[2] / tot[0]:.0f}%)")


if __name__ == "__main__":
    main()
