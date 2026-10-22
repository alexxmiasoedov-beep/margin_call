"""t.me/s/cryptocoddee: листаем назад (before=id) и сохраняем страницы raw/p_<id>.html."""
import subprocess, re, os, time, sys
CH = "cryptocoddee"
def get(u):
    for k in range(6):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", "Mozilla/5.0", u], capture_output=True, text=True)
        if r.returncode == 0 and "tgme_widget_message" in r.stdout: return r.stdout
        if r.returncode == 0 and "tgme_channel_info" in r.stdout and "tgme_widget_message" not in r.stdout: return r.stdout
        time.sleep(2 + 3 * k)
    return None
before = None; n = 0
while True:
    u = f"https://t.me/s/{CH}" + (f"?before={before}" if before else "")
    h = get(u)
    if h is None: print("ошибка", u, flush=True); break
    ids = [int(x) for x in re.findall(rf'data-post="{CH}/(\d+)"', h)]
    if not ids: print("конец", before, flush=True); break
    open(f"raw/p_{min(ids)}.html", "w").write(h); n += 1
    if n % 20 == 0: print(n, "страниц, до id", min(ids), flush=True)
    if before is not None and min(ids) >= before: print("не листается", before, flush=True); break
    before = min(ids)
    if before <= 1: break
    time.sleep(0.5)
print("готово", n, flush=True)
