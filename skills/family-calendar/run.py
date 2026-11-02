"""把家裡的接送表同步到 Google 日曆（家人共用的「紀家接送」日曆）。只用標準庫。

資料來源是本機的 events JSON（不進 repo，裡面是家人行程），格式見同資料夾的
events.example.json。小鳥（Hermes）負責維護那份 JSON，這支只負責「讓日曆跟 JSON 一致」：

- 每個行程用 key 辨識，存在 Google 事件的 extendedProperties.private.juju_key
- JSON 有、日曆沒有 → 新增；內容不同 → 更新；日曆有但 JSON 已刪 → 刪除
- 只碰自己建的事件（private.juju=family-calendar），家人手動加的行程不會動

用法：
  python3 skills/family-calendar/run.py            # 只列出計畫，不改日曆（預設）
  python3 skills/family-calendar/run.py --apply    # 真的寫入
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from juju import load_env  # noqa: E402

API = "https://www.googleapis.com/calendar/v3"
TAG = "family-calendar"
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def hermes_home():
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


# ---------- OAuth：沿用 Hermes google-workspace 技能產生的 token ----------

def access_token(token_file):
    data = json.loads(token_file.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({
        "client_id": data["client_id"],
        "client_secret": data["client_secret"],
        "refresh_token": data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    uri = data.get("token_uri") or "https://oauth2.googleapis.com/token"
    try:
        with urllib.request.urlopen(urllib.request.Request(uri, data=body), timeout=20) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Google token 更新失敗 HTTP {e.code}：{e.read().decode(errors='replace')[:200]}")


def call(token, method, path, params=None, body=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Calendar API {method} {path} 失敗 HTTP {e.code}：{e.read().decode(errors='replace')[:300]}")


# ---------- JSON → Google 事件 ----------

def first_on_or_after(start, byday):
    """byday 例如 'MO' 或 'MO,TU'：回傳 start 當天或之後第一個符合的日期。"""
    wanted = {WEEKDAYS.index(d.strip()) for d in byday.split(",")}
    day = start
    while day.weekday() not in wanted:
        day += dt.timedelta(days=1)
    return day


def build(ev, tz, weekly_start):
    """把一筆 JSON 行程轉成 Google 事件 body（不含 extendedProperties）。"""
    desc = "\n".join(x for x in [ev.get("who") and f"接送：{ev['who']}", ev.get("note")] if x)
    body = {"summary": ev["title"], "description": desc}
    if ev.get("all_day"):
        start = dt.date.fromisoformat(ev["date"])
        end = dt.date.fromisoformat(ev.get("end_date", ev["date"])) + dt.timedelta(days=1)
        body["start"] = {"date": start.isoformat()}
        body["end"] = {"date": end.isoformat()}
        return body
    if ev.get("weekday"):
        day = first_on_or_after(dt.date.fromisoformat(ev.get("from", weekly_start)), ev["weekday"])
        rule = f"RRULE:FREQ=WEEKLY;BYDAY={ev['weekday'].replace(' ', '')}"
        if ev.get("until"):
            rule += ";UNTIL=" + ev["until"].replace("-", "") + "T155959Z"  # 台灣時間當天 23:59:59
        body["recurrence"] = [rule]
    else:
        day = dt.date.fromisoformat(ev["date"])
    body["start"] = {"dateTime": f"{day}T{ev['start']}:00", "timeZone": tz}
    body["end"] = {"dateTime": f"{day}T{ev.get('end', ev['start'])}:00", "timeZone": tz}
    return body


def fingerprint(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def desired_events(data):
    tz = data.get("timezone", "Asia/Taipei")
    weekly_start = data.get("weekly_start", dt.date.today().isoformat())
    out, seen = {}, set()
    for ev in data["events"]:
        key = ev["key"]
        if key in seen:
            raise SystemExit(f"events JSON 裡 key 重複：{key}")
        seen.add(key)
        body = build(ev, tz, weekly_start)
        h = fingerprint(body)
        body["extendedProperties"] = {"private": {"juju": TAG, "juju_key": key, "juju_hash": h}}
        out[key] = (body, h)
    return out


def existing_events(token, cal):
    items, page = [], None
    while True:
        params = {"privateExtendedProperty": f"juju={TAG}", "maxResults": 2500, "showDeleted": "false"}
        if page:
            params["pageToken"] = page
        res = call(token, "GET", f"/calendars/{urllib.parse.quote(cal)}/events", params)
        items += res.get("items", [])
        page = res.get("nextPageToken")
        if not page:
            break
    return {e["extendedProperties"]["private"]["juju_key"]: e for e in items}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="真的寫入日曆（預設只列計畫）")
    args = ap.parse_args()

    try:
        load_env()
    except SystemExit:
        pass  # 沒有 repo 的 .env 也能跑，改用環境變數
    events_file = Path(os.environ.get("FAMILY_CALENDAR_EVENTS") or hermes_home() / "notes" / "calendar-events.json")
    token_file = Path(os.environ.get("GOOGLE_TOKEN_FILE") or hermes_home() / "google_token.json")
    cal = os.environ.get("FAMILY_CALENDAR_ID", "")

    want = desired_events(json.loads(events_file.read_text(encoding="utf-8")))

    if not token_file.exists() or not cal:
        print("⚠️ 還沒完成 Google 授權或沒設 FAMILY_CALENDAR_ID，以下假設日曆是空的：")
        have, token = {}, None
    else:
        token = access_token(token_file)
        have = existing_events(token, cal)

    creates = [k for k in want if k not in have]
    updates = [k for k in want if k in have
               and have[k]["extendedProperties"]["private"].get("juju_hash") != want[k][1]]
    deletes = [k for k in have if k not in want]

    for label, keys in (("新增", creates), ("更新", updates), ("刪除", deletes)):
        for k in keys:
            title = (want.get(k) or ({"summary": have[k].get("summary")},))[0]["summary"]
            print(f"{label}：{title}（{k}）")
    if not (creates or updates or deletes):
        print("日曆已經是最新的，不用改。")
        return
    print(f"共 新增 {len(creates)}、更新 {len(updates)}、刪除 {len(deletes)}")

    if not args.apply:
        print("（只是預覽；加 --apply 才會寫入）")
        return
    if token is None:
        raise SystemExit("沒有授權，不能 --apply")

    path = f"/calendars/{urllib.parse.quote(cal)}/events"
    for k in creates:
        call(token, "POST", path, body=want[k][0])
    for k in updates:
        call(token, "PUT", f"{path}/{have[k]['id']}", body=want[k][0])
    for k in deletes:
        call(token, "DELETE", f"{path}/{have[k]['id']}")
    print("✅ 已同步到 Google 日曆")


if __name__ == "__main__":
    main()
