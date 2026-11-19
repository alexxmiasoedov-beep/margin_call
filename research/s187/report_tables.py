"""s187 — таблицы отчёта reports/каталог.md: каталог топа (catalog.csv + ручной разбор), сводка блоков, частоты
сигналов отобранных (freq.pkl из check.py). Печатает Markdown в stdout: python3 report_tables.py > таблицы.md.

Ручной разбор (A) — по исходникам из /home/user/mc_data/s187/pine и описаниям авторов: блоки, явный сигнал, перерисовка.
Коды блоков — как в analyze.py: MA, OSC, VOLA, VOL, STRUCT, ML, TIME, PAT; «—» у закрытых без описания логики."""
import csv
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# uuid → (блоки, сигнал, перерисовка/заглядывание)
A = {
    # ---------------- индикаторы
    "CnB3fSph": ("STRUCT", "алерты BOS/CHoCH, OB, FVG, EQH/EQL", "нет у BOS/CHoCH (пивоты +5/+50 баров, метка у пивота)"),
    "nqQ1DT5a": ("VOLA OSC", "нет меток; правило автора — выход из сжатия", "нет"),
    "r6dAP7yi": ("VOLA", "Buy/Sell + алерты", "нет"),
    "OQx7vju0": ("MA OSC", "точки пересечения MACD/сигнальной", "нет на своём ТФ; старший ТФ — security v1 с заглядыванием"),
    "JDFoWQbL": ("STRUCT VOL", "метки «B», алерты пробоя", "нет; пивоты +15, линии сдвинуты на −16"),
    "og7JPrRA": ("VOLA", "подсветка дна (без продаж)", "нет"),
    "DkE7UniD": ("STRUCT", "MSB + алерт", "нет; блоки рисуются в прошлом"),
    "n8ss8BID": ("VOLA", "Buy/Sell + алерты", "нет"),
    "2KE8wTuF": ("OSC", "нет меток; правило автора — пересечения в зонах", "нет"),
    "nW5oGfdO": ("TIME STRUCT", "нет (сессии, уровни)", "нет"),
    "IYL88A1N": ("STRUCT VOLA", "метки «B» + алерты", "линии с backpainting (сдвиг 14), метки — нет"),
    "Ej53t8Wv": ("STRUCT", "алерты пробоя канала", "пивоты +10; каналы пересчитываются"),
    "RQnLfaNE": ("STRUCT", "нет (уровни свингов)", "закрыт; по описанию — пивоты"),
    "Uz2AJ0i4": ("STRUCT VOL", "ромбы «пробой/удержание» зоны", "пивоты; метки со сдвигом −1"),
    "VTPMMOrx": ("OSC", "нет (DI±, ADX, порог 20)", "нет"),
    "fYHlrAoz": ("—", "сигналы Confirmation/Contrarian", "закрыт; «оптимальная чувствительность» подбирается по истории графика"),
    "bkb6vZDz": ("TIME VOL", "нет", "нет"),
    "1S2VOnJP": ("STRUCT VOL", "нет (зоны ликвидности)", "пивоты +14"),
    "R8g2YHdg": ("STRUCT", "алерт «новый OB — не сигнал»", "рисует со сдвигом −N"),
    "KvGhxGxY": ("STRUCT VOL", "алерты OB/смягчение", "пивоты объёма +5; блоки в прошлом"),
    "G8b8t2er": ("STRUCT", "нет (FVG)", "закрыт; FVG — 3-свечной разрыв"),
    "WhBzgfDu": ("ML OSC", "Buy/Sell + алерты", "да: last_bar_index задаёт окно обучения"),
    "zX3fvduH": ("MA PAT", "3 Line Strike, «Big Ass Candle»", "нет"),
    "OQs2lVvr": ("MA", "нет (цвет средней)", "старший ТФ — security v1 с заглядыванием"),
    "Iko0E2kL": ("ML VOLA", "▲▼ + алерты", "да по умолчанию (двусторонняя регрессия); есть режим без перерисовки"),
    "vcsWo8mh": ("PAT", "15 фигур, метки + алерты", "нет"),
    "qIKR3tbN": ("VOLA", "нет", "нет"),
    "Hvk5WzPi": ("VOLA VOL", "алерты пробоя канала", "нет по коду; панель на последнем баре"),
    "Qt7fqntR": ("VOLA", "нет (вероятности уровней)", "статистика по всей истории графика"),
    "ZGl2xWym": ("STRUCT", "BOS/CHoCH/CHoCH+, OB", "закрыт"),
    "ib4uqBJx": ("STRUCT TIME", "▲▼ у пивотов, MSS", "режим Present от last_bar_index; пивоты"),
    "CLk71Qgy": ("ML VOLA", "▲▼ + алерты", "нет"),
    "Qk4vBbfL": ("STRUCT", "alert() на снятие", "режим Present; пивоты"),
    "PmIP7HAZ": ("STRUCT", "BOS/CHoCH", "закрыт; по описанию — пивоты"),
    "piIbWMpY": ("STRUCT", "▲▼ у прошлых свингов", "метки задним числом"),
    "wP7WWjLL": ("ML VOLA", "метки смены тренда", "нет (кластеры на последних 10 000 барах)"),
    "n8AGnIZd": ("OSC VOL STRUCT", "метки + алерты дивергенций", "сигнал — нет; старые метки стираются"),
    "AqXxNS7j": ("VOLA", "Buy/Sell + алерты", "нет"),
    "GE7tSQK1": ("MA", "стрелки входа", "нет"),
    "o50NYLAZ": ("VOLA VOL", "BUY/SELL + алерты", "нет"),
    "L0AIiLvH": ("STRUCT VOLA", "Buy/Sell + алерты", "нет (пивоты 2/2 для центра)"),
    "48ZWvclR": ("MA", "нет", "нет"),
    "va09eWAp": ("STRUCT", "алерты пробоя уровня", "пивоты"),
    "eXUYLaGv": ("STRUCT", "нет (линии тренда)", "пивоты; линии в прошлом"),
    "aZACDmTC": ("STRUCT", "метки BoS/OB/FVG", "пивоты; сдвиг"),
    "1JKqmEKy": ("MA", "нет (цвет ленты)", "нет"),
    "GHnJs0X8": ("PAT", "подсветка пин-баров и др. (по умолчанию выкл.)", "нет"),
    "BEhT6Syv": ("—", "Buy/Sell", "по приглашению; по описанию — SuperTrend с фильтром Калмана + полосы VWMA"),
    "EvkXjgyw": ("STRUCT", "треугольники + алерты пробоя", "нет (пивоты +5)"),
    "S2ClgBm5": ("VOL STRUCT TIME", "alert()", "фракталы старших ТФ через security"),
    "9kY5NlHJ": ("TIME STRUCT", "нет", "пивоты"),
    "RADlhsKE": ("OSC", "нет (цвет свечей по RSI)", "нет"),
    "MhlDpfdS": ("VOL", "нет меток; правило автора — пересечение нуля", "нет"),
    "mFWSBQhC": ("TIME", "нет (свеча старшего ТФ)", "закрыт"),
    "jWY4Uiez": ("STRUCT", "алерты FVG", "нет на своём ТФ"),
    "kIY0znXs": ("VOL", "нет (профиль)", "на последнем баре"),
    "UpWXXsbC": ("VOL STRUCT", "нет", "видимый диапазон экрана"),
    "bLdpFVuq": ("STRUCT VOL", "алерты OB", "окно от last_bar_index"),
    "jvNJYfbL": ("STRUCT", "метки BOS/CHoCH", "isrealtime/last_bar_index"),
    "Oun5v3Zq": ("MA OSC VOLA", "конструктор Buy/Sell", "зависит от выбранных условий"),
    "7Q5CbHhr": ("STRUCT", "метки", "пивоты"),
    "xy4EFLtD": ("STRUCT VOLA", "нет (коробки)", "только последние N баров"),
    "r3VrWAO4": ("VOL", "нет", "видимый диапазон (опция)"),
    "Msm4SjwI": ("OSC VOL", "кружки Buy/Sell, дивергенции", "кружки — нет; дивергенции со сдвигом −2"),
    "xOm7jSPf": ("OSC MA", "цвет линии RSI(2)", "нет"),
    "kqKEuQpn": ("TIME", "нет (пивотные уровни)", "нет (security с [1])"),
    "OxJJqZiN": ("STRUCT", "▲▼ у пивотов", "метки на пивоте — видны через length баров"),
    "tV3rCaJ9": ("TIME VOL", "нет", "нет"),
    "JRqryeJ5": ("STRUCT", "метки снятия ликвидности", "пивоты (снятие ликвидности проверено в s155)"),
    "CapG3ivf": ("STRUCT OSC PAT", "алерты", "опция перерисовки"),
    "jFQn4jYZ": ("OSC", "кружки на пересечениях WT", "нет"),
    "WZ8B1FIW": ("STRUCT", "alert() фигур", "зигзаг; опция перерисовки"),
    "6WDeQiyp": ("STRUCT VOL", "нет", "на последнем баре"),
    "Wylw98ue": ("OSC", "подсветка пересечений", "старший ТФ — security v1"),
    "Z1byay68": ("STRUCT VOL", "alert()", "видимый диапазон"),
    "hg92pFwS": ("MA", "алерты смены цвета", "нет на своём ТФ"),
    "zVhoDQME": ("MA VOLA", "алерты BUY/SELL", "нет"),
    "utCRHZeP": ("VOL STRUCT", "alert()", "пивоты; на последнем баре"),
    "mBKF9wUj": ("OSC", "подсветка зон", "старший ТФ — security v1"),
    "pbeoiKh5": ("STRUCT", "BOS/CHoCH", "закрыт"),
    "n1co3drh": ("MA", "алерты Buy/Sell", "нет"),
    "fCqLTp6r": ("TIME", "метки пробоя диапазона открытия", "нет"),
    "W5N54CeR": ("VOL", "нет", "на последнем баре"),
    "egfSfN1y": ("MA", "Buy/Sell", "нет"),
    "iOrhpIqc": ("STRUCT VOL", "метки пробоя/ретеста", "пивоты"),
    "bcWGvngm": ("MA", "Buy/Sell", "старший ТФ — security v1 с заглядыванием"),
    "yxEJ4Dxw": ("STRUCT PAT", "метки у свингов", "метки задним числом"),
    "4IYKX938": ("OSC", "нет (цвета)", "нет"),
    "ZtoavozZ": ("STRUCT TIME", "сделки ICT", "закрыт"),
    "hb6J9iHI": ("STRUCT", "Long/Short", "видимый диапазон; пивоты"),
    "Qwj6TO5I": ("VOL", "alert()", "видимый диапазон"),
    "pB5nv16J": ("STRUCT", "Long/Short Entry", "нет"),
    "lj8djt1n": ("STRUCT", "алерты HH/LL", "да: последнее колено зигзага перерисовывается"),
    "CfqnRBHd": ("TIME", "нет", "закрыт"),
    "yXJBwibN": ("STRUCT VOL", "нет", "нет"),
    "fH6e5TuN": ("OSC", "нет (RSI 5 − RSI 14; дивергенции нет)", "нет"),
    "ILps3wnk": ("STRUCT", "нет (зоны)", "закрыт"),
    "YdtBEh4F": ("STRUCT", "нет (зоны)", "пивоты"),
    "sU9molfV": ("MA VOLA", "алерты BUY/SELL", "нет"),
    "sXFWVpmg": ("MA VOLA OSC", "Buy/Sell", "нет (подтверждение на закрытии)"),
    # ---------------- стратегии
    "uCV8I4xA": ("VOLA OSC", "strategy.entry (стоп-заявка)", "нет"),
    "yMCa3XZD": ("MA OSC", "strategy.entry (стоп-заявка)", "нет"),
    "P5Gu6F8k": ("VOLA", "strategy.entry", "нет"),
    "iifAsfrq": ("MA OSC", "лонг: MACD ↑ и RSI < 30 пять баров назад", "закрыт"),
    "nHGK4Qtp": ("MA VOLA", "strategy.entry", "нет"),
    "MvlwAzSg": ("MA VOLA", "strategy.entry + бот", "нет"),
    "Q9OQye4C": ("MA", "strategy.entry", "нет"),
    "RpYoQCVJ": ("OSC", "strategy.entry", "нет"),
    "j9rq1wQq": ("MA", "strategy.entry", "нет"),
    "2lGyzYkC": ("—", "шаблон стратегии", "—"),
    "6ZReHYKn": ("MA", "strategy.entry", "нет"),
    "i3Uc79fF": ("OSC VOLA VOL", "strategy.entry (только лонг)", "нет; правила подобраны на BTC 15m"),
    "qSLcZSyw": ("OSC STRUCT", "strategy.entry", "вход через 5 баров после пивота, метки сдвинуты на −5"),
    "RJBjyl2W": ("MA TIME", "strategy.entry", "дневная свеча через security без [1] — история ≠ реальное время"),
    "zWX2G809": ("—", "Buy/Sell", "закрыт"),
    "vObmEraY": ("MA", "strategy.entry", "да: старший ТФ с lookahead_on без [1] (по умолчанию)"),
    "rLkjr2sQ": ("STRUCT", "strategy.entry (двойная вершина/дно)", "нет"),
    "VKMgZdYr": ("VOLA", "strategy.entry", "нет"),
    "EjLwVtgp": ("STRUCT", "strategy.entry", "фракталы +2 бара, отрисовка со сдвигом"),
    "HDSdFMa3": ("VOLA OSC", "strategy.entry", "нет"),
    "eENf7NpJ": ("MA VOLA", "strategy.entry", "нет"),
    "oY725jQw": ("ML", "strategy.entry", "нет (security с [1])"),
    "G5ro3y87": ("OSC", "strategy.entry", "нет"),
    "XLGBqrZq": ("MA", "strategy.entry", "нет"),
    "0zX3PYZi": ("—", "«90% прибыли»", "по приглашению"),
    "9MJO3AgE": ("MA OSC", "пример алертов", "нет"),
    "VO6DY8s1": ("MA", "strategy.entry", "нет"),
    "4ORGCiTh": ("MA OSC VOLA", "strategy.entry", "нет"),
    "yvDyq0pv": ("TIME", "strategy.entry по фазам Луны", "нет"),
    "3wdQu7P3": ("VOLA VOL", "strategy.entry", "нет"),
    "ISb50FOM": ("—", "strategy.entry", "закрыт"),
    "IGJPEi7L": ("OSC", "strategy.entry", "нет"),
    "IHVPG6TS": ("—", "пример стоп/тейк", "—"),
    "HPbRZvsV": ("MA VOLA", "strategy.entry", "нет"),
    "zopumZ8a": ("VOLA OSC", "strategy.entry", "нет"),
    "Pu38F2pB": ("—", "адаптер бэктеста", "—"),
    "Q1O23zJP": ("STRUCT", "strategy.entry", "нет"),
    "RHagaXIp": ("VOLA", "strategy.entry", "нет"),
    "XK8XbDhT": ("TIME", "strategy.entry", "да: security('D', close) в Pine v2 видит закрытие текущего дня"),
    "9wda3yUw": ("MA", "strategy.entry", "нет (исправленная версия)"),
}


def md_escape(s):
    return str(s).replace("|", "/")


def catalog_tables():
    rows = list(csv.DictReader(open(os.path.join(HERE, "catalog.csv"), encoding="utf-8")))
    out = []
    for kind, title in (("indicator", "Индикаторы (топ-100 по бустам за всё время)"),
                        ("strategy", "Стратегии (топ-40)")):
        out.append(f"\n**{title}**\n")
        out.append("| № | Скрипт | Автор | Бусты | Доступ | Pine | Дата | Блоки | Явный сигнал | Перерисовка / заглядывание |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            if r["kind"] != kind:
                continue
            b, s, rp = A.get(r["uuid"], ("?", "?", "?"))
            name = md_escape(r["name"])[:70]
            acc = {"открытый": "откр.", "защищённый": "закр.", "по приглашению": "приглаш."}[r["access"]]
            pv = r["pine"].split(".")[0] if r["pine"] else "—"
            bst = f"{int(r['boosts']):,}".replace(",", " ")
            out.append(f"| {r['rank']} | [{name}]({r['url']}) | {r['author']} | {bst} | {acc} | {pv} | "
                       f"{r['created'][:7]} | {b} | {s} | {rp} |")
    return "\n".join(out)


def block_stats():
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, "catalog.csv"), encoding="utf-8"))
            if r["kind"] == "indicator"]
    cnt = {}
    sig = 0
    for r in rows:
        b, s, _ = A[r["uuid"]]
        for x in b.split():
            if x != "—":
                cnt[x] = cnt.get(x, 0) + 1
        if not s.startswith("нет"):
            sig += 1
    return cnt, sig, len(rows)


def freq_table():
    import indicators as I
    F = pd.read_pickle("/home/user/mc_data/s187/freq.pkl")
    out = []
    pers = ["2020–2022", "2022–2024", "2024–2026"]
    for tf in ("1h", "4h"):
        out.append(f"\n**{tf}**: сигналов в месяц на одну ликвидную монету (buy / sell) и всего в месяц по всем ликвидным "
                   f"альтам (buy + sell)\n")
        out.append("| Скрипт | " + " | ".join(f"{p}: на монету" for p in pers) + " | " +
                   " | ".join(f"{p}: всего" for p in pers) + " |")
        out.append("|---|" + "---|" * 6)
        for nm in I.REG:
            cells1, cells2 = [], []
            for p in pers:
                q = F[(F.ind == nm) & (F.per == p) & (F.tf == tf)]
                if len(q):
                    q = q.iloc[0]
                    cells1.append(f"{q.buy_cm:.1f} / {q.sell_cm:.1f}".replace(".", ","))
                    cells2.append(f"{q.buy_m + q.sell_m:,.0f}".replace(",", " "))
                else:
                    cells1.append("—")
                    cells2.append("—")
            out.append(f"| {nm} | " + " | ".join(cells1) + " | " + " | ".join(cells2) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("catalog", "all"):
        print(catalog_tables())
    if what in ("stats", "all"):
        c, s, n = block_stats()
        print("\nБлоки в топ-100 индикаторов:", sorted(c.items(), key=lambda x: -x[1]), f"; с явным сигналом {s} из {n}")
    if what in ("freq", "all"):
        print(freq_table())
