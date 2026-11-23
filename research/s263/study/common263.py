"""s263 — общие функции: загрузка выборки TradFi (extract.py), сессии базовых рынков, праздники, группы контрактов."""
import datetime
import os
import pickle
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

SHM = "/dev/shm/s263"
UTC = datetime.timezone.utc
NY = ZoneInfo("America/New_York")
SEOUL = ZoneInfo("Asia/Seoul")
HKT = ZoneInfo("Asia/Hong_Kong")
DAY = 86400

# Праздники NYSE 2025–2026 (полный выходной) и сокращённые дни (закрытие 13:00 ET)
NYSE_HOLI = {"2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
             "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"}
NYSE_HALF = {"2025-12-24", "2026-11-27", "2026-12-24"}
# Плечевые и обратные ETF (по названию фонда; список Binance исключённых из дивидендов + прочие плечевые)
LEV = {"SOXL", "SOXS", "TQQQ", "SQQQ", "NVDL", "TSLL", "MSTU", "MUU", "KORU", "TMF", "TZA", "TBT", "AMDL", "UVXY",
       "SKUU", "SKDD", "SNXX", "MVLL", "BWET", "AGPU", "SHAZ", "SECZ", "BOT", "BNC", "DRAM", "RAM", "STXX", "CRML",
       "ARTY", "ZCSH", "LYTE", "KSTR", "BSP", "CYPH", "TWST", "INTW", "WEN", "PENG", "FWDI", "BBX", "QNTX"}
ETF = {"SPY", "QQQ", "IWM", "EWY", "EWJ", "EWT", "EWZ", "EWZS", "EIDO", "SMH", "SOXX", "XBI", "XLE", "GDX", "URNM",
       "IGV", "IBIT", "BITO", "USDEX"}


def load_k():
    return pickle.load(open(f"{SHM}/tf_k.pkl", "rb"))


def load_f():
    return pickle.load(open(f"{SHM}/tf_f.pkl", "rb"))


def load_meta():
    m = pd.read_csv("s263/tf_meta.csv")
    return m


def group(sym, ut):
    if ut == "EQUITY":
        if sym in LEV:
            return "US_LEV"
        if sym in ETF:
            return "US_ETF"
        return "US_STOCK"
    return ut


def et_parts(t):
    """Массив UTC-секунд → DataFrame: местное время Нью-Йорка (дата, день недели, минуты от полуночи)."""
    idx = pd.to_datetime(np.asarray(t, dtype="int64"), unit="s", utc=True).tz_convert(NY)
    return pd.DataFrame({"date": idx.strftime("%Y-%m-%d"), "wd": idx.weekday, "mins": idx.hour * 60 + idx.minute})


def us_session(t):
    """Сессия базового рынка акций США для момента t (открытие 15-мин свечи), по времени Нью-Йорка:
    REG 9:30–16:00 (сокращённый день — до 13:00), PRE 4:00–9:30, POST 16:00–20:00, ON 20:00–4:00 (вс 20:00 – пт 4:00),
    WKND — пт 20:00 – вс 20:00, HOL — праздник NYSE (с 20:00 накануне до 20:00 дня праздника)."""
    p = et_parts(t)
    out = np.empty(len(p), dtype=object)
    wd, mins, date = p.wd.values, p.mins.values, p.date.values
    for i in range(len(p)):
        d, w, m = date[i], wd[i], mins[i]
        # «торговый день» для ночной сессии после 20:00 — следующий день
        if m >= 20 * 60:
            nd = (datetime.date.fromisoformat(d) + datetime.timedelta(1))
            nds, nw = nd.isoformat(), nd.weekday()
        else:
            nds, nw = d, w
        if nw >= 5 or (w == 4 and m >= 20 * 60) or (w == 6 and m < 20 * 60):
            out[i] = "WKND"
            continue
        if nds in NYSE_HOLI:
            out[i] = "HOL"
            continue
        if m >= 20 * 60 or m < 4 * 60:
            out[i] = "ON"
        elif m < 9 * 60 + 30:
            out[i] = "PRE"
        elif m < (13 * 60 if d in NYSE_HALF else 16 * 60):
            out[i] = "REG"
        else:
            out[i] = "POST"
    return out


def cme_session(t):
    """Сырьё (CME Globex): OPEN вс 18:00 – пт 17:00 ET, кроме перерыва 17:00–18:00 ET пн–чт (BREAK); WKND — пт 17:00 –
    вс 18:00 ET; праздники CME здесь не размечены отдельно."""
    p = et_parts(t)
    wd, mins = p.wd.values, p.mins.values
    out = np.where((wd == 5) | ((wd == 4) & (mins >= 17 * 60)) | ((wd == 6) & (mins < 18 * 60)), "WKND",
                   np.where((mins >= 17 * 60) & (mins < 18 * 60), "BREAK", "OPEN"))
    return out


def kr_session(t):
    """Корея (KRX): OPEN пн–пт 09:00–15:20 KST = 00:00–06:20 UTC; иначе CLOSED; WKND — сб, вс (по Сеулу)."""
    idx = pd.to_datetime(np.asarray(t, dtype="int64"), unit="s", utc=True).tz_convert(SEOUL)
    m = idx.hour * 60 + idx.minute
    wd = idx.weekday
    return np.where(wd >= 5, "WKND", np.where((m >= 9 * 60) & (m < 15 * 60 + 20), "OPEN", "CLOSED"))


def hk_session(t):
    """Гонконг (HKEX): OPEN 09:30–12:00 и 13:00–16:00 HKT; LUNCH 12:00–13:00; иначе CLOSED; WKND — сб, вс."""
    idx = pd.to_datetime(np.asarray(t, dtype="int64"), unit="s", utc=True).tz_convert(HKT)
    m = idx.hour * 60 + idx.minute
    wd = idx.weekday
    op = ((m >= 9 * 60 + 30) & (m < 12 * 60)) | ((m >= 13 * 60) & (m < 16 * 60))
    return np.where(wd >= 5, "WKND", np.where(op, "OPEN", np.where((m >= 12 * 60) & (m < 13 * 60), "LUNCH", "CLOSED")))


def cn_session(t):
    """Китай (SSE/SZSE): OPEN 09:30–11:30 и 13:00–14:57 по Пекину (как Гонконг, UTC+8)."""
    idx = pd.to_datetime(np.asarray(t, dtype="int64"), unit="s", utc=True).tz_convert(HKT)
    m = idx.hour * 60 + idx.minute
    wd = idx.weekday
    op = ((m >= 9 * 60 + 30) & (m < 11 * 60 + 30)) | ((m >= 13 * 60) & (m < 14 * 60 + 57))
    return np.where(wd >= 5, "WKND", np.where(op, "OPEN", "CLOSED"))


def fmt_ts(t):
    return datetime.datetime.fromtimestamp(int(t), UTC).strftime("%Y-%m-%d %H:%M")
