"""讓 LINE 一直連得到 Hermes gateway：顧著 cloudflared 臨時 tunnel，網址換了就自動改 LINE webhook。

臨時 tunnel（trycloudflare）每次啟動網址都不同，斷線後就作廢，不會自己接回。
這支常駐（launchd KeepAlive）做三件事：
1. 開 cloudflared，抓到新網址後用 LINE API 改 webhook URL
2. 每分鐘從外網打一次 health；連續失敗 MAX_FAILS 次或 cloudflared 結束就重開
3. Mac 剛睡醒時馬上檢查，不通就直接重開（睡太久 tunnel 通常已作廢）
4. gateway 本機 health 不通時不動 tunnel（那是 Hermes 的事，由 ai.hermes.gateway 負責）

用法：python3 -u skills/line-tunnel/run.py
"""

import json
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from juju import load_env, require  # noqa: E402

LOCAL = "http://127.0.0.1:8646"
HEALTH = "/line/webhook/health"
WEBHOOK = "/line/webhook"
CHECK_EVERY = 60     # 秒
MAX_FAILS = 3        # 外網 health 連續失敗幾次就重開
START_TIMEOUT = 60   # 等 cloudflared 給網址、連上的秒數
TICK = 5             # 多久看一次時鐘；牆上時鐘一次跳很多 = 剛睡醒
WAKE_GAP = 30        # 比 TICK 多出這麼多秒就當作睡過（macOS 睡眠時 monotonic 會停，所以用 time.time）
WAKE_SETTLE = 10     # 睡醒後先等 Wi-Fi 接回再檢查
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

proc = None


def log(msg):
    print(f"{time.strftime('%F %T')} {msg}", flush=True)


def healthy(base):
    try:
        with urllib.request.urlopen(base + HEALTH, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def line_api(method, path, body=None):
    req = urllib.request.Request(
        "https://api.line.me" + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + require("LINE_CHANNEL_ACCESS_TOKEN"),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]


def set_webhook(url):
    status, detail = line_api("PUT", "/v2/bot/channel/webhook/endpoint", {"endpoint": url + WEBHOOK})
    if status != 200:
        log(f"改 webhook 失敗 HTTP {status}: {detail}")
        return False
    status, detail = line_api("GET", "/v2/bot/channel/webhook/endpoint")
    log(f"webhook 已改：{detail}")
    return status == 200 and url in detail


def start_tunnel():
    """開 cloudflared，回傳 (process, url)；失敗回傳 (process, None)。"""
    p = subprocess.Popen(
        ["cloudflared", "tunnel", "--no-autoupdate", "--url", LOCAL],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    found = {"url": None}
    ready = threading.Event()

    def pump():
        for line in p.stdout:
            line = line.rstrip()
            print("  cloudflared| " + line, flush=True)
            m = URL_RE.search(line)
            if m and not found["url"]:
                found["url"] = m.group(0)
            if "Registered tunnel connection" in line:
                ready.set()

    threading.Thread(target=pump, daemon=True).start()
    ready.wait(START_TIMEOUT)
    return p, (found["url"] if ready.is_set() else None)


def stop_tunnel(p):
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


def on_term(signum, frame):
    log("收到結束訊號，關掉 tunnel")
    stop_tunnel(proc)
    sys.exit(0)


def wait_public(url, tries=20):
    """新網址的 DNS 要一點時間才生效；太早查會吃到負快取，所以先等一下再開始打。"""
    time.sleep(10)
    err = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url + HEALTH, timeout=10) as resp:
                if resp.status == 200:
                    return True
        except Exception as e:
            err = e
        time.sleep(3)
    log(f"外網 health 一直不通：{err!r}")
    return False


def main():
    global proc
    load_env()
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    backoff = 5

    while True:
        if not healthy(LOCAL):
            log("gateway 本機 health 不通，等它起來再開 tunnel")
            time.sleep(CHECK_EVERY)
            continue

        proc, url = start_tunnel()
        if not url or not wait_public(url) or not set_webhook(url):
            log(f"tunnel 沒起來（url={url}），{backoff} 秒後重試")
            stop_tunnel(proc)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue
        log(f"上線：{url}")
        backoff = 5

        fails = 0
        last = time.time()
        due = last + CHECK_EVERY
        while proc.poll() is None:
            time.sleep(TICK)
            now = time.time()
            woke = now - last > TICK + WAKE_GAP
            if woke:
                log(f"Mac 剛睡醒（{int(now - last)} 秒沒動靜），{WAKE_SETTLE} 秒後檢查")
                time.sleep(WAKE_SETTLE)
                now = time.time()
            last = now
            if not woke and now < due:
                continue
            due = now + CHECK_EVERY

            if healthy(url):
                fails = 0
            elif not healthy(LOCAL):
                log("gateway 本機不通，tunnel 先不動")
            else:
                fails = MAX_FAILS if woke else fails + 1
                log(f"外網 health 失敗 {fails}/{MAX_FAILS}")
                if fails >= MAX_FAILS:
                    break
        log(f"tunnel 斷了（cloudflared exit={proc.poll()}），重開")
        stop_tunnel(proc)


if __name__ == "__main__":
    main()
