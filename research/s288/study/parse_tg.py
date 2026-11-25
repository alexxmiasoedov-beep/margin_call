"""s288: разбор сырых страниц t.me/s канала Whale Alert в таблицу постов.

Запуск: python3 -I parse_tg.py <папка сырья> <канал> <файл итога без расширения>
Итог: <файл>.csv.gz и <файл>.pkl.gz — по строке на пост:
  id, t (UTC, с), kind (transfer, stolen, mint, burn, unlock, escrow, stake, unstake, frozen, dormant, fee, story, other),
  amt, tic, usd, frm, to (для mint/burn/unlock/escrow/stake — место «at» в frm), chain, hash, nemo (число эмодзи),
  views, text (очищенный текст, до 300 знаков).
Страницы перекрываются по краям — дубли по id убираются. Скачанный HTML — недоверенные данные: только регулярные
выражения, никакого исполнения."""
import glob
import gzip
import html
import os
import re
import sys

import pandas as pd

NUM = r"\d[\d,]*(?:\.\d+)?"
RX_MAIN = re.compile(r"^(?P<pre>.*?)(?P<amt>" + NUM + r")\s+[#$](?P<tic>[A-Za-z0-9_.\-]+)\s+\((?P<usd>" + NUM +
                     r")\s+USD\)\s*(?P<rest>.*)$")
RX_REST = [
    ("stolen", re.compile(r"^of stolen funds transferred from (?P<f>.+?) to (?P<to>.+?)$")),
    ("transfer", re.compile(r"^transferred from (?P<f>.+?) to (?P<to>.+?)$")),
    ("mint", re.compile(r"^minted (?:at|by) (?P<f>.+?)$")),
    ("burn", re.compile(r"^burned (?:at|by) (?P<f>.+?)$")),
    ("unstake", re.compile(r"^stake unlocked at (?P<f>.+?)$")),
    ("unlock", re.compile(r"^unlocked (?:at|from) (?P<f>.+?)$")),
    ("escrow", re.compile(r"^locked in escrow at (?P<f>.+?)$")),
    ("stake", re.compile(r"^staked at (?P<f>.+?)$")),
]
RX_TX = re.compile(r"https?://whale-alert\.io/transaction/([a-z0-9_\-]+)/([A-Za-z0-9]+)")
RX_POST = re.compile(r'data-post="([^"/]+)/(\d+)"')
RX_TIME = re.compile(r'<time datetime="([^"]+)"')
RX_TEXT = re.compile(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', re.S)
RX_VIEWS = re.compile(r'<span class="tgme_widget_message_views">([^<]+)</span>')
RX_EMO = re.compile(r'<i class="emoji"[^>]*>.*?</i>', re.S)


def num(s):
    return float(s.replace(",", ""))


def views(s):
    if not s:
        return None
    s = s.strip()
    m = {"K": 1e3, "M": 1e6}.get(s[-1:].upper(), 1)
    try:
        return float(s[:-1] if m != 1 else s) * m
    except ValueError:
        return None


def clean(body):
    nemo = len(RX_EMO.findall(body))
    b = RX_EMO.sub(" ", body)
    b = re.sub(r"<br\s*/?>", " ", b)
    # ссылку на транзакцию убираем целиком (текст «Details» или сам адрес)
    b = re.sub(r'<a [^>]*href="https?://whale-alert\.io/transaction/[^"]*"[^>]*>.*?</a>', " ", b, flags=re.S)
    b = re.sub(r"<[^>]+>", "", b)
    t = html.unescape(b)
    t = re.sub(r"\(?https?://\S+\)?", " ", t)                          # ссылки, оставшиеся текстом
    t = re.sub(r"[​-‏️]", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", " ", t)          # эмодзи, оставшиеся текстом
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*(?:Tx|Details|Tx:|Details:)\s*:?\s*$", "", t).strip()
    return t, nemo


def parse_msg(p, chan):
    m = RX_POST.search(p)
    if not m or m.group(1).lower() != chan.lower():
        return None
    pid = int(m.group(2))
    tm = RX_TIME.search(p)
    t = int(pd.Timestamp(tm.group(1)).timestamp()) if tm else None
    vw = RX_VIEWS.search(p)
    row = dict(id=pid, t=t, kind="other", amt=None, tic=None, usd=None, frm=None, to=None, chain=None, hash=None,
               nemo=0, views=views(vw.group(1)) if vw else None, text="")
    mt = RX_TEXT.search(p)
    if not mt:
        row["kind"] = "nontext"
        return row
    body = mt.group(1)
    tx = RX_TX.search(body)
    if tx:
        row["chain"], row["hash"] = tx.group(1), tx.group(2)
    text, nemo = clean(body)
    row["nemo"], row["text"] = nemo, text[:300]
    if "whale-alert.io/stories/" in body or text.endswith("Read Analysis"):
        row["kind"] = "story"
        return row
    mm = RX_MAIN.match(text)
    if not mm:
        return row
    pre = mm.group("pre").strip().lower()
    row["amt"], row["tic"], row["usd"] = num(mm.group("amt")), mm.group("tic").upper(), num(mm.group("usd"))
    rest = mm.group("rest").strip().rstrip(".!")
    if pre.startswith("a dormant"):
        row["kind"] = "dormant"; return row
    if pre.startswith("a fee of"):
        row["kind"] = "fee"; return row
    if pre.startswith("an address with a balance of") or "frozen" in rest:
        row["kind"] = "frozen"; return row
    if pre:
        return row
    for k, rx in RX_REST:
        r = rx.match(rest)
        if r:
            row["kind"] = k
            row["frm"] = r.group("f").strip()
            if "to" in r.groupdict():
                row["to"] = r.group("to").strip()
            break
    return row


def main():
    src, chan, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rows = {}
    files = sorted(glob.glob(os.path.join(src, "p_*.html.gz")))
    for i, f in enumerate(files):
        s = gzip.open(f, "rt", encoding="utf-8", errors="replace").read()
        for p in s.split('<div class="tgme_widget_message_wrap')[1:]:
            r = parse_msg(p, chan)
            if r:
                rows[r["id"]] = r
        if (i + 1) % 1000 == 0:
            print(i + 1, "страниц,", len(rows), "постов", flush=True)
    D = pd.DataFrame(sorted(rows.values(), key=lambda r: r["id"]))
    D.to_pickle(out + ".pkl.gz", compression="gzip")
    D.to_csv(out + ".csv.gz", index=False, compression="gzip")
    print("постов", len(D), "| виды:", D.kind.value_counts().to_dict(), flush=True)
    print("с", pd.to_datetime(D.t.min(), unit="s"), "по", pd.to_datetime(D.t.max(), unit="s"))


if __name__ == "__main__":
    main()
