"""s288: вежливая выгрузка публичного канала Telegram через t.me/s (без ключа и логина).

Запуск: python3 -I fetch_tg.py <канал> <папка сырья> [мин. интервал, с] [до id]
- идёт от новых постов к старым (?before=<id>), по 20 постов на страницу;
- не чаще одного запроса в `interval` секунд (по умолчанию 1,05 с от начала до начала);
- 429 и 5xx — пауза и повтор (5 → 10 → 20 → … до 300 с), после 8 неудач подряд — выход с сообщением;
- продолжение с места остановки: state.json в папке сырья (следующий before);
- каждая страница — p_<before>.html.gz; разбор — отдельно (parse_tg.py).
"""
import gzip, json, os, re, sys, time, urllib.error, urllib.request

UA = "research-script/1.0"


def main():
    chan = sys.argv[1]
    out = sys.argv[2]
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.05
    stop_at = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    os.makedirs(out, exist_ok=True)
    stf = os.path.join(out, "state.json")
    st = json.load(open(stf)) if os.path.exists(stf) else {"before": None, "pages": 0, "done": False}
    if st.get("done"):
        print("уже выгружено", flush=True)
        return
    pat = re.compile(r'data-post="%s/(\d+)"' % re.escape(chan))
    last = 0.0
    fails = 0
    t0 = time.time()
    while True:
        b = st["before"]
        url = "https://t.me/s/%s" % chan + ("?before=%d" % b if b else "")
        wait = interval - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        last = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40)
            body = r.read()
            code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
            body = b""
        except Exception as e:  # сеть: обрыв, таймаут
            code = -1
            body = b""
            err = repr(e)[:200]
        if code != 200:
            fails += 1
            if fails > 8:
                print("стоп: %d неудач подряд, код %s, before=%s" % (fails, code, b), flush=True)
                break
            p = min(300, 5 * 2 ** (fails - 1))
            print("код %s (%s), пауза %d с" % (code, err if code == -1 else "", p), flush=True)
            time.sleep(p)
            continue
        txt = body.decode("utf-8", "replace")
        ids = [int(x) for x in pat.findall(txt)]
        if not ids:
            # пустая страница: либо конец, либо сбой выдачи — повторим один раз с паузой
            fails += 1
            if fails > 3:
                print("пустая страница before=%s — конец выдачи" % b, flush=True)
                st["done"] = True
                json.dump(st, open(stf, "w"))
                break
            time.sleep(10)
            continue
        fails = 0
        name = "p_%s.html.gz" % (b if b else "top")
        with gzip.open(os.path.join(out, name), "wb", compresslevel=6) as f:
            f.write(body)
        mn = min(ids)
        st["pages"] += 1
        if b is not None and mn >= b:
            print("before не уменьшился (%s → %s) — стоп" % (b, mn), flush=True)
            break
        st["before"] = mn
        if mn <= stop_at:
            st["done"] = True
        json.dump(st, open(stf, "w"))
        if st["pages"] % 50 == 0:
            tm = re.findall(r'<time datetime="([^"]+)"', txt)
            print("стр %d, before=%d, %s, %.0f с" % (st["pages"], mn, tm[0] if tm else "?", time.time() - t0), flush=True)
        if st["done"]:
            print("готово: %d страниц" % st["pages"], flush=True)
            break


if __name__ == "__main__":
    main()
