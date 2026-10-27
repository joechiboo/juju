"""Mac 電量提醒：用電池且電量低於門檻時推一則 LINE，每輪放電每個門檻只推一次。

用法：
  python3 skills/battery-alert/run.py            # 檢查，必要時推播
  python3 skills/battery-alert/run.py --dry-run  # 只印出目前狀態與會不會推
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import juju  # noqa: E402

THRESHOLDS = (20, 10)  # 由高到低
STATE_FILE = juju.ROOT / "data" / "battery-alert.json"


def read_battery():
    """回傳 (電量%, 是否在用電池, 剩餘時間字串或 None)。"""
    out = subprocess.run(["pmset", "-g", "batt"], check=True, capture_output=True, text=True).stdout
    m = re.search(r"(\d+)%; ([^;]+);\s*(\S+)?", out)
    if not m:
        raise SystemExit(f"讀不到電池資訊：{out.strip()}")
    percent, status, remaining = int(m.group(1)), m.group(2).strip(), m.group(3)
    on_battery = "Battery Power" in out and status == "discharging"
    if remaining in (None, "(no", "0:00"):
        remaining = None
    return percent, on_battery, remaining


def load_alerted():
    try:
        return set(json.loads(STATE_FILE.read_text())["alerted"])
    except (FileNotFoundError, KeyError, ValueError):
        return set()


def save_alerted(alerted):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"alerted": sorted(alerted)}))


def main():
    dry_run = "--dry-run" in sys.argv
    percent, on_battery, remaining = read_battery()
    alerted = load_alerted()

    if not on_battery:
        # 插上電就重新計算，下一輪放電會再提醒
        if alerted and not dry_run:
            save_alerted(set())
        print(f"{percent}%，接電中，不提醒")
        return

    due = [t for t in THRESHOLDS if percent <= t and t not in alerted]
    if not due:
        print(f"{percent}%，用電池，尚未到新的門檻（已提醒：{sorted(alerted) or '無'}）")
        return

    level = min(due)
    message = f"🐦 啾！Mac 電量剩 {percent}%"
    if remaining:
        message += f"，大約還能撐 {remaining}"
    message += "\n快去插電，不然我會睡著 💤"

    if dry_run:
        print(f"會推播：\n{message}")
        return
    juju.load_env()
    juju.line_push(message)
    save_alerted(alerted | {t for t in THRESHOLDS if t >= level})
    print(f"{percent}%，已推到 LINE")


if __name__ == "__main__":
    main()
