"""s181 — публичные ончейн-трекеры в Telegram (t.me/s без аккаунта): Lookonchain (по разборам Arkham) и OnchainLens.
Выгрузка постов с 01.10.2024 назад от последнего (параметр before), кэш /home/user/mc_data/s181/tg/<канал>.json.
Частота в месяц постов о продажах и заводах на биржи команд, фондов проектов и казначейств (по тикеру $XXX
с перпом Binance), отдельно — о разлоках и маркетмейкерах. Только частоты; цены и доходы не считаются."""
import html
import json
import os
import re
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

TG = f"{C.OUT}/tg"
os.makedirs(TG, exist_ok=True)
STOP = pd.Timestamp("2024-10-01", tz="UTC")
MSG = re.compile(r'data-post="[^/]+/(\d+)".*?(?:tgme_widget_message_text[^>]*>(.*?)</div>)?.*?datetime="([^"]+)"', re.S)

WHO = re.compile(r"foundation|treasury|\bteam\b|\bdev(eloper)?s?\b|deployer|\bproject\b|\bdao\b|multisig|vesting|"
                 r"ecosystem fund|\binvestor|\bvc\b|venture|labs\b|co-?founder|founder", re.I)
ACT = re.compile(r"deposit|sent|sold|dump|sell|transferr?ed .{0,60}(binance|okx|bybit|coinbase|kraken|bitget|gate|"
                 r"kucoin|htx|upbit|bithumb|wintermute|falconx|flowdesk|gsr|cumberland|amber)", re.I)
UNL = re.compile(r"unlock", re.I)
MMK = re.compile(r"wintermute|gsr\b|flowdesk|amber group|cumberland|falconx|dwf|jump trading|market maker", re.I)
TICK = re.compile(r"\$([A-Z0-9]{2,12})\b")


def crawl(ch, max_pages=3000):
    path = f"{TG}/{ch}.json"
    posts = json.load(open(path)) if os.path.exists(path) else []
    seen = {p["id"] for p in posts}
    before = min(seen) if seen else None
    if posts and pd.Timestamp(min(p["date"] for p in posts)) <= STOP:
        return posts
    for k in range(max_pages):
        url = f"https://t.me/s/{ch}" + (f"?before={before}" if before else "")
        code, raw = C.get(url, headers={"Accept": "text/html"})
        if code != 200 or not raw:
            time.sleep(20)
            continue
        t = raw.decode("utf-8", "replace")
        blocks = t.split('class="tgme_widget_message_wrap')[1:]
        got = []
        for b in blocks:
            m = re.search(r'data-post="[^/]+/(\d+)"', b)
            d = re.search(r'datetime="([^"]+)"', b)
            x = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
            if not m or not d:
                continue
            i = int(m.group(1))
            txt = html.unescape(re.sub(r"<[^>]+>", " ", x.group(1))) if x else ""
            got.append(dict(id=i, date=d.group(1), text=re.sub(r"\s+", " ", txt)[:1500]))
        new = [g for g in got if g["id"] not in seen]
        if not got:
            break
        for g in new:
            seen.add(g["id"])
        posts += new
        before = min(g["id"] for g in got)
        oldest = pd.Timestamp(min(g["date"] for g in got))
        if k % 50 == 0:
            print(f"  {ch}: страниц {k}, постов {len(posts)}, до {oldest.date()}", flush=True)
            json.dump(posts, open(path, "w"))
        if oldest <= STOP or before <= 1:
            break
        time.sleep(0.8)
    json.dump(posts, open(path, "w"))
    return posts


def main():
    P = C.perps()
    B = {C.base(k).upper() for k in P}
    MAJ = {"BTC", "ETH", "USDT", "USDC", "SOL", "BNB", "XRP"}
    for ch in ("lookonchainchannel", "onchainlens"):
        posts = crawl(ch)
        df = pd.DataFrame(posts)
        df["t"] = pd.to_datetime(df.date, utc=True)
        df = df[df.t >= STOP]
        months = (df.t.max() - df.t.min()).days / 30.4
        tick = df.text.map(lambda s: {x for x in TICK.findall(s) if x in B and x not in MAJ})
        alt = df[tick.map(bool)]
        who = alt[alt.text.str.contains(WHO) & alt.text.str.contains(ACT)]
        print(f"\n{ch}: постов {len(df)} за {months:.1f} мес. ({df.t.min().date()} – {df.t.max().date()}); "
              f"с тикером альта-перпа {len(alt)} ({len(alt) / months:.0f} в месяц)")
        print(f"  команда/фонд/казна/инвестор + завод или продажа: {len(who)} ({len(who) / months:.1f} в месяц), "
              f"монет {len(set().union(*tick[who.index])) if len(who) else 0}")
        print(f"  …из них про разлок: {int(who.text.str.contains(UNL).sum())}; про маркетмейкера: "
              f"{int(who.text.str.contains(MMK).sum())}")
        f = who.text.str.contains(r"foundation|treasury|\bdao\b|ecosystem fund", case=False)
        print(f"  только фонд/казна/DAO: {int(f.sum())} ({f.sum() / months:.1f} в месяц)")
        print(f"  по месяцам (все «команда/фонд/казна»):", who.t.dt.strftime("%Y-%m").value_counts().sort_index().to_dict())
        for r in who[f].head(12).itertuples():
            print(f"   {r.t.date()} {r.text[:170]}")


if __name__ == "__main__":
    main()
