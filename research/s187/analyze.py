"""s187 — разбор исходников Pine топа: строительные блоки, явные сигналы, признаки перерисовки и заглядывания вперёд.

Читает catalog.csv и исходники /home/user/mc_data/s187/pine/<uuid>.pine; пишет blocks.csv (метаданные, без кода).
Признаки — поиском по коду (регулярные выражения), затем проверены вручную для отобранных (см. reports/каталог.md).

Блоки: MA — средние/тренд; OSC — осцилляторы; VOLA — ATR, BB, stdev, каналы; VOL — объём/поток/профиль;
STRUCT — пивоты, зигзаг, BOS/CHoCH, ордер-блоки, FVG, ликвидность, уровни; ML — ядра, kNN, k-средние, регрессии;
TIME — сессии, время, HTF-свечи; PAT — свечные фигуры.
Риски: SEC_LA — request.security с lookahead_on; SEC — security на другом таймфрейме без защиты [1]; PIVOT — пивоты
(сигнал через right баров); OFFSET — отрисовка со сдвигом назад (offset < 0, x = bar_index − n); LASTBAR — расчёт
от last_bar_index / barstate.islast (история зависит от длины графика); RT — barstate.isrealtime/isconfirmed;
VISIBLE — видимый диапазон (chart.left_visible_bar_time…); REPAINT_OPT — у скрипта есть переключатель перерисовки."""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PINE = "/home/user/mc_data/s187/pine"

BLOCKS = {
    "MA": r"\b(ta\.)?(sma|ema|wma|hma|vwma|rma|alma|swma|dema|tema|zlema|kama|t3|lsma|vidya)\s*\(|moving average",
    "OSC": r"\b(ta\.)?(rsi|stoch|cci|macd|mfi|wpr|mom|roc|cmo|tsi|dmi|adx|ao)\s*\(|wavetrend|\bwt1\b|oscillator",
    "VOLA": r"\b(ta\.)?(atr|stdev|bb|bbw|kc|tr|variance|dev)\s*[\(\b]|\btr\b|bollinger|keltner|donchian|supertrend",
    "VOL": r"\bvolume\b|\bobv\b|vwap|profile|\bpoc\b|delta",
    "STRUCT": r"pivothigh|pivotlow|zigzag|\bbos\b|choch|order.?block|\bfvg\b|fair value|liquidity|swing|breaker|"
              r"support|resistance|mitigat|structure",
    "ML": r"kernel|nadaraya|knn|neighbo|k-?means|cluster|machine learning|lorentz|regression|centroid",
    "TIME": r"session|killzone|time\(|timeframe\.change|dayofweek|hour\b|request\.security\(.*[\"']D[\"']",
    "PAT": r"engulf|harami|doji|hammer|pin ?bar|inside ?bar|outside ?bar|morning star|evening star|shooting",
}


def feats(src):
    s = src or ""
    low = s.lower()
    code = "\n".join(x for x in s.splitlines() if not x.strip().startswith("//"))
    lc = code.lower()
    blocks = [b for b, rx in BLOCKS.items() if re.search(rx, lc)]
    sec = re.findall(r"(?:request\.)?security\s*\(([^\n]*)", code)
    risks = []
    if re.search(r"lookahead\s*=\s*(barmerge\.)?lookahead_on|lookahead\s*=\s*true", lc):
        risks.append("SEC_LA")
    elif sec and not re.search(r"barmerge\.lookahead_on", lc):
        tf_args = [x for x in sec if not re.search(r"timeframe\.period|\bperiod\b", x)]
        if tf_args:
            risks.append("SEC")
    if re.search(r"pivothigh|pivotlow", lc):
        risks.append("PIVOT")
    if re.search(r"offset\s*=\s*-|bar_index\s*-\s*\w+|bar_index\[\w+\]", lc):
        risks.append("OFFSET")
    if re.search(r"last_bar_index|barstate\.islast", lc):
        risks.append("LASTBAR")
    if re.search(r"barstate\.isrealtime|barstate\.isconfirmed|calc_on_every_tick", lc):
        risks.append("RT")
    if re.search(r"chart\.left_visible|chart\.right_visible|visible", lc):
        risks.append("VISIBLE")
    if re.search(r"repaint", low):
        risks.append("REPAINT_OPT")
    sig = []
    n_alert = len(re.findall(r"alertcondition\s*\(", code))
    if n_alert:
        sig.append(f"alert×{n_alert}")
    if re.search(r"plotshape\s*\([^\n]*(buy|sell|long|short|bull|bear|▲|▼)", lc):
        sig.append("plotshape buy/sell")
    if re.search(r"strategy\.entry", lc):
        sig.append("strategy.entry")
    if re.search(r"label\.new\s*\([^\n]*(buy|sell|long|short)", lc):
        sig.append("label buy/sell")
    if re.search(r"\balert\s*\(", code):
        sig.append("alert()")
    return blocks, risks, sig


def main():
    rows = list(csv.DictReader(open(os.path.join(HERE, "catalog.csv"), encoding="utf-8")))
    out = []
    for r in rows:
        p = os.path.join(PINE, r["uuid"] + ".pine")
        src = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        b, rk, sg = feats(src) if src else ([], [], [])
        out.append(dict(kind=r["kind"], rank=r["rank"], name=r["name"], author=r["author"], boosts=r["boosts"],
                        access=r["access"], pine=r["pine"], blocks=" ".join(b), signals=" ".join(sg),
                        risks=" ".join(rk), uuid=r["uuid"]))
    with open(os.path.join(HERE, "blocks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(len(out), "строк → blocks.csv")


if __name__ == "__main__":
    main()
