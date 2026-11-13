"""s27 — позиции трейдеров Hyperliquid из сделок (s27/fills/<адрес>.json): позиция после сделки = позиция до неё ± размер.
Монета Hyperliquid → фьючерс Binance (s22/grid.pkl): kPEPE → 1000PEPE, RNDR → RENDER, MATIC → POL; монеты HIP-3 («:»),
спот («@», «/») — без пары. Итог — s27/pos.pkl:
  coins  — список фьючерсов Binance;
  series — {(адрес, монета): (времена с, позиции после сделок)}, позиция известна с первой сделки по монете;
  opens  — массив событий открытия (время с, номер монеты, сторона ±1, номер адреса): из нуля или переворотом;
  first  — {адрес: время первой доступной сделки} (у счетов с 10 тыс.+ сделок раньше неё позиции неизвестны).
Запуск из папки с данными."""
import glob
import json
import os
import pickle
import numpy as np

GR = pickle.load(open("s22/grid.pkl", "rb"))
ROW = GR["row"]
REN = {"RNDR": "RENDER", "MATIC": "POL"}


def binance(coin):
    if ":" in coin or "@" in coin or "/" in coin:
        return None
    cands = []
    if coin.startswith("k") and coin[1:].isupper():
        cands += ["1000" + coin[1:], coin[1:]]
    cands += [coin, REN.get(coin, coin), "1000" + coin]
    for c in cands:
        if c in ROW:
            return c
    return None


def build():
    files = sorted(glob.glob("s27/fills/*.json"))
    coins, cidx, series, opens, first = [], {}, {}, [], {}
    for ai, f in enumerate(files):
        a = os.path.basename(f)[:-5]
        F = json.load(open(f))
        if not F:
            continue
        F.sort(key=lambda x: x[0])
        first[a] = F[0][0] / 1000
        per = {}
        for t, coin, side, px, sz, start, cpnl, fee, d in F:
            b = binance(coin)
            if b is None:
                continue
            new = start + (sz if side == "B" else -sz)
            if abs(new) < 1e-12 * max(1.0, abs(start)):
                new = 0.0
            per.setdefault(b, []).append((t / 1000, new, start))
            if new != 0 and (start == 0 or np.sign(start) != np.sign(new)):
                if b not in cidx:
                    cidx[b] = len(coins); coins.append(b)
                opens.append((t / 1000, cidx[b], int(np.sign(new)), ai))
        for b, x in per.items():
            x = np.array(x)
            # позиция до первой сделки известна (start), после — значения new
            tt = np.r_[x[0, 0] - 1e-3, x[:, 0]]; pp = np.r_[x[0, 2], x[:, 1]]
            series[(a, b)] = (tt, pp)
            if b not in cidx:
                cidx[b] = len(coins); coins.append(b)
    O = np.array(opens, dtype=np.float64) if opens else np.zeros((0, 4))
    out = dict(coins=coins, cidx=cidx, series=series, opens=O, first=first,
               addrs=[os.path.basename(f)[:-5] for f in files])
    pickle.dump(out, open("s27/pos.pkl", "wb"))
    return out


if __name__ == "__main__":
    P = build()
    print(f"счетов {len(P['first'])}, монет с парой на Binance {len(P['coins'])}, рядов позиций {len(P['series'])}, "
          f"открытий {len(P['opens'])}")
