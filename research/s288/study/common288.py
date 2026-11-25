"""s288 — общее: периоды, классы меток Whale Alert (биржа, кастоди, эмитент, DeFi, неизвестный…), классы монет,
перпы Binance по датам, монеты в обращении (CMC топ-200 s136 + токены s160).
Запуск скриптов — из /home/user/mc_data (python3 -I <repo>/research/s288/study/<скрипт>.py)."""
import glob
import json
import os
import re

import numpy as np
import pandas as pd

DAY = 86400
OUT, TMP = "/home/user/mc_data/s288", "/dev/shm/s288"


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


PER = {"2020–2022": (ts("2020-10-01"), ts("2022-10-01")),
       "2022–2024": (ts("2022-10-01"), ts("2024-10-01")),
       "2024–2026": (ts("2024-10-01"), ts("2026-10-19")),
       "свежий": (ts("2026-10-19"), ts("2026-11-25"))}


def months(p):
    a, b = PER[p]
    return (b - a) / DAY / 30.4375


def period_of(t):
    t = np.asarray(t, float)
    out = np.full(len(t), None, object)
    for p, (a, b) in PER.items():
        out[(t >= a) & (t < b)] = p
    return out


# ---------- монеты ----------
STABLE = {"USDT", "USDC", "BUSD", "PAX", "USDP", "TUSD", "HUSD", "GUSD", "DAI", "PYUSD", "FDUSD", "USDE", "USDS", "USD1",
          "RLUSD", "EURC", "EURT", "EURS", "USDD", "FRAX", "USDG", "USD0", "SUSD", "LUSD", "USDK", "USDX", "USDB",
          "EUROC", "XAUT", "PAXG", "USDTB", "USDR", "EURR", "AUSD", "USDH", "USDF", "USR", "DOLA", "CUSD", "USDN",
          "BGBP", "QCAD", "NUSD", "UST", "USTC", "MIM", "USDJ", "FEI", "TRYB", "BIDR", "IDRT", "SAI", "BKRW"}
GOLD = {"XAUT", "PAXG"}
WRAPPED = {"WBTC", "BTCB", "WETH", "STETH", "WSTETH", "CBBTC", "TBTC", "RENBTC", "HBTC", "WEETH", "METH", "RETH", "CBETH",
           "BETH", "EZETH", "RSETH", "SOLVBTC", "LBTC", "FBTC", "ENZOBTC", "WBNB", "WTRX", "WSOL", "JITOSOL", "MSOL",
           "BNSOL", "WEETH", "SAVAX", "STLINK"}


def norm_hash(h):
    """Хеш для сопоставления: нижний регистр без префикса 0x (в Telegram 2019–2022 гг. хеши Ethereum — без 0x)."""
    if not isinstance(h, str):
        return ""
    h = h.strip().lower()
    return h[2:] if h.startswith("0x") else h


def coin_class(tic):
    t = tic.upper() if isinstance(tic, str) else ""
    if t in GOLD:
        return "gold"
    if t in STABLE:
        return "stable"
    if t == "BTC":
        return "btc"
    if t == "ETH":
        return "eth"
    if t in WRAPPED:
        return "wrapped"
    return "alt"


# ---------- метки ----------
def norm_label(s):
    """Метка поста или архива → нижний регистр без #, точек и пробелов-дублей; хвосты Deposits/Withdrawals/… отдельно."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return "", ""
    x = str(s).strip().lower().replace("#", "")
    x = re.sub(r"\s+", " ", x)
    suf = ""
    m = re.match(r"^(.*?)\s+(deposits?|withdrawals?|coldstorage|cold storage|cold wallet|hot wallet|reserves?)$", x)
    if m:
        x, suf = m.group(1), m.group(2)
    return x, suf


CEX = {
    "binance": "Binance", "binanceus": "Binance.US", "binance us": "Binance.US", "binance.us": "Binance.US",
    "coinbase": "Coinbase", "bitfinex": "Bitfinex", "huobi": "HTX", "huobi global": "HTX", "htx": "HTX",
    "ftx": "FTX", "ftx us": "FTX", "okex": "OKX", "okx": "OKX", "okcoin": "OKX", "kraken": "Kraken",
    "bitstamp": "Bitstamp", "gemini": "Gemini", "cryptocom": "Crypto.com", "crypto.com": "Crypto.com",
    "bittrex": "Bittrex", "poloniex": "Poloniex", "robinhood": "Robinhood", "bitso": "Bitso", "bithumb": "Bithumb",
    "kucoin": "KuCoin", "bybit": "Bybit", "upbit": "Upbit", "bitflyer": "bitFlyer", "bitflyer.jp": "bitFlyer",
    "gateio": "Gate", "gate.io": "Gate", "gate": "Gate", "bitbank": "bitbank", "http://bitbank.com": "bitbank",
    "renrenbit": "RenrenBit", "hitbtc": "HitBTC", "bitmex": "BitMEX", "bitget": "Bitget", "zb": "ZB",
    "uphold": "Uphold", "coinone": "Coinone", "bitvavo": "Bitvavo", "coincheck": "Coincheck", "coinsph": "Coins.ph",
    "gopax": "Gopax", "bigone": "BigONE", "deribit": "Deribit", "coinbene": "CoinBene", "btcturk": "BtcTurk",
    "korbit": "Korbit", "mexc": "MEXC", "bitx": "Luno", "luno": "Luno", "coinfloor": "Coinfloor", "deepcoin": "Deepcoin",
    "bitpanda": "Bitpanda", "hotbit": "Hotbit", "bitmax": "AscendEX", "ascendex": "AscendEX", "bitkub": "Bitkub",
    "bitrue": "Bitrue", "paribu": "Paribu", "xapo": "Xapo", "cashapp": "Cash App", "bitpay": "BitPay",
    "liquid": "Liquid", "bitlish": "Bitlish", "exmo": "EXMO", "lbank": "LBank", "bitstamp.net": "Bitstamp",
    "indodax": "Indodax", "wazirx": "WazirX", "coindcx": "CoinDCX", "bitopro": "BitoPro", "max": "MAX",
    "zaif": "Zaif", "bitbay": "BitBay", "zonda": "BitBay", "btcmarkets": "BTC Markets", "coinspot": "CoinSpot",
    "independent reserve": "Independent Reserve", "cex.io": "CEX.IO", "cexio": "CEX.IO", "yobit": "YoBit",
    "bitkub exchange": "Bitkub", "whitebit": "WhiteBIT", "htx global": "HTX", "bingx": "BingX", "phemex": "Phemex",
    "unconfirmed exchange": "unconfirmed", "coinex": "CoinEx", "bitforex": "BitForex", "probit": "ProBit",
    "bitmart": "BitMart", "mt gox": "Mt.Gox", "mtgox": "Mt.Gox", "mtgox cold wallet": "Mt.Gox",
    "paxful": "Paxful", "coinlist": "CoinList", "revolut": "Revolut", "voyager": "Voyager", "fixedfloat": "FixedFloat",
    "hashkey": "HashKey", "valr": "VALR", "swissborg": "SwissBorg", "bitpanda pro": "Bitpanda", "okcoin japan": "OKX",
}
MINER_RX = re.compile(r"antpool|f2pool|poolin|viabtc|btc\.com|foundry|marathon|mining|miner|slush|braiins|spiderpool|luxor")
INST = {  # кастоди, прайм-брокеры, ОТС и маркетмейкеры, фонды и ETF
    "coinbase institutional": "Coinbase Inst.", "coinbase custody": "Coinbase Inst.", "coinbase prime": "Coinbase Inst.",
    "ceffu": "Ceffu", "falconx": "FalconX", "cumberland": "Cumberland", "galaxy digital": "Galaxy",
    "wintermute": "Wintermute", "alameda research": "Alameda", "jump trading": "Jump", "b2c2": "B2C2",
    "genesis trading": "Genesis", "cobo": "Cobo", "zero hash": "Zero Hash", "abraxas": "Abraxas",
    "bitwise etf": "ETF", "anchorage": "Anchorage", "bitgo": "BitGo", "copper": "Copper", "fireblocks": "Fireblocks",
    "nexo": "Nexo", "blockfi": "BlockFi", "celsius network": "Celsius", "celsius": "Celsius", "paxos": "Paxos",
    "paypal": "PayPal", "blockfolio": "FTX", "ftx estate account": "FTX", "amber group": "Amber", "matrixport": "Matrixport",
    "grayscale": "ETF", "blackrock": "ETF", "fidelity": "ETF", "flow traders": "Flow Traders", "dwf labs": "DWF",
    "gsr": "GSR", "qcp capital": "QCP", "hidden road": "Hidden Road", "fidelity custody": "ETF", "ishares": "ETF",
    "metaalpha": "MetaAlpha",
}
ISSUER = {  # эмитенты и их казна, сжигатели, фонды сетей
    "tether treasury": "Tether", "usdc treasury": "Circle", "usdc incinerator": "Circle", "pax treasury": "Paxos",
    "paxos treasury": "Paxos", "husd treasury": "HUSD", "husd incinerator": "HUSD", "wbtc treasury": "WBTC",
    "tusd treasury": "TUSD", "trueusd treasury": "TUSD", "busd treasury": "Paxos", "gusd treasury": "Gemini$",
    "zilliqa incinerator": "other", "burn address": "burn", "ripple": "Ripple", "ripple escrow wallet": "Ripple",
    "ripple otc distribution wallet": "Ripple", "xrp ii wallet": "Ripple", "jed mccaleb wallet": "Ripple",
    "jed mccaleb settlement": "Ripple", "frax": "Frax", "ethena": "Ethena", "trondao": "Tron", "tron foundation": "Tron",
    "btcb reserve": "Binance", "pyusd treasury": "Paxos", "fdusd treasury": "FDUSD", "first digital": "FDUSD",
    "usdd treasury": "Tron", "sky": "Sky", "makerdao": "Sky", "paypal treasury": "Paxos", "rlusd treasury": "Ripple",
    "bat ugp reserve": "other", "stellar development foundation": "SDF", "binance-peg": "Binance",
}
DEFI_RX = re.compile(r"aave|compound|beacon|lido|wrapped|uniswap|curve|maker|spark|justlend|polygon|arbit|hypercore|"
                     r"kelp|etherfi|liquity|sushi|dsproxy|bridge|kinetiq|hyperunit|staking|vault|pool|dao|swap|"
                     r"morpho|pendle|eigen|lending|1inch|0x|gnosis|safe|hyperliquid|wormhole|portal|multichain|"
                     r"optimism|base|zksync|starknet|linea|scroll|mantle|blast|layerzero|stargate|across|celer")
HACK_RX = re.compile(r"hack|stolen|exploit|scam|ransom|blackmail|fraud|lazarus|heist|drainer|attacker")
UNKNOWN_RX = re.compile(r"^(unknown( new)?( wallet)?|unknown whale \d+|multiple addresses|multiple wallets|)$")


def entity(label):
    """Класс метки: unknown, cex, inst, issuer, defi, hack, other; и имя (для бирж — каноническое)."""
    x, suf = norm_label(label)
    if UNKNOWN_RX.match(x) or x.startswith("unknown"):
        return "unknown", ""
    if x in CEX:
        return "cex", CEX[x]
    if x in INST:
        return "inst", INST[x]
    if x in ISSUER:
        return "issuer", ISSUER[x]
    if x.startswith("sdf ") or x.startswith("ripple "):
        return "issuer", "SDF" if x.startswith("sdf ") else "Ripple"
    if HACK_RX.search(x):
        return "hack", x
    if MINER_RX.search(x):
        return "other", "майнер"
    if x.endswith(" treasury") or x.endswith(" incinerator"):
        return "issuer", x
    if DEFI_RX.search(x):
        return "defi", x
    # хвосты бирж: «binance 14», «okex cold», «huobi 2» и т. п.
    head = x.split(" ")[0]
    if head in CEX and head not in ("max", "liquid", "gate"):
        return "cex", CEX[head]
    return "other", x


# ---------- перпы Binance ----------
def perps():
    """База перпа → (первая, последняя свеча с оборотом); перпы, живые на конец свечей (≈ 19.11.2026), — до бесконечности."""
    P = json.load(open(f"{OUT}/perps.json"))
    end = max(v[1] for v in P.values())
    return {b: (v[0], v[1] if v[1] < end - 2 * DAY else 4e9) for b, v in P.items()}


ALIAS = {"MATIC": "POL", "RNDR": "RENDER", "FTM": "S", "MKR": "SKY", "EOS": "A", "LUNA": "LUNA2", "LUNC": "LUNA",
         "BCC": "BCH", "BCHABC": "BCH", "XBT": "BTC", "BTT": "BTTC", "KNC": "KNC", "LEND": "AAVE", "AGIX": "FET",
         "OCEAN": "FET", "GALA": "GALA", "MC": "MC", "AMP": "AMP"}


def base_of(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs or "")
    return m.group(2) if m and not m.group(2)[0].isdigit() else fs


def has_perp(P, tic, t):
    """Был ли перп Binance у монеты в момент t (по первой и последней свече с оборотом, ±1 сут)."""
    t = float(t)
    for k in (tic, ALIAS.get(tic)):
        if k and k in P:
            a, b = P[k]
            if a - DAY <= t <= b + DAY:
                return True
    return False


# ---------- монеты в обращении ----------
class Circ:
    """Монеты в обращении на дату: дневные снимки CMC топ-200 (s136/raw, с 01.07.2020) по тикеру, при совпадении тикеров —
    монета с ценой ближе всего к цене алерта; запас — ряды s160/circ по id CMC токенов s160."""

    def __init__(self, syms=None):
        self.snap = {}
        for p in sorted(glob.glob("s136/raw/*.json")):
            d = os.path.basename(p)[:10]
            rows = json.load(open(p))
            m = {}
            for r in rows:
                s = (r[1] or "").upper()
                if syms is not None and s not in syms:
                    continue
                if r[4] and r[5]:
                    m.setdefault(s, []).append((float(r[4]), float(r[5]), float(r[6] or 0), int(r[2] or 999)))
            self.snap[d] = m
        self.days = sorted(self.snap)
        ids = json.load(open("s160/cmc_ids.json"))
        self.tok = {}
        for v in ids.values():
            f = f"s160/circ/{v['id']}.json"
            if os.path.exists(f):
                a = json.load(open(f))
                self.tok.setdefault(v["sym"].upper(), {r[0]: (float(r[1]), float(r[2] or 0)) for r in a if r[1]})

    def get(self, sym, t, px=None):
        """(монет в обращении, цена CMC, оборот CMC за 24 ч или None) на сутки t (или ближайшие прошлые 3 сут);
        px — цена алерта для выбора монеты при совпадении тикеров."""
        s = (sym or "").upper()
        d = pd.Timestamp(int(t), unit="s").strftime("%Y-%m-%d")
        i = np.searchsorted(self.days, d, "right") - 1
        for j in range(i, max(i - 3, -1), -1):
            c = self.snap[self.days[j]].get(s)
            if c:
                if px and len(c) > 1:
                    c = sorted(c, key=lambda z: abs(np.log(z[1] / px)) if z[1] > 0 else 99)
                return c[0][0], c[0][1], c[0][2]
        z = self.tok.get(s)
        if z:
            for k in range(4):
                dd = (pd.Timestamp(int(t), unit="s") - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
                if dd in z:
                    return z[dd][0], z[dd][1], None
        return None, None, None
