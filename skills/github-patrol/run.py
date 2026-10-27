"""GitHub repo 巡檢：列出有 open issue/PR 的 repo，以及正在冷掉的 side project，推到 LINE。

用法：
  python3 skills/github-patrol/run.py            # 推到 LINE
  python3 skills/github-patrol/run.py --dry-run  # 只印出訊息
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
import juju  # noqa: E402

OWNER = "joechiboo"
COOLING_DAYS = (30, 180)  # 多久沒 push 算「冷掉中」；超過上限視為已封存，不再提醒
MAX_ITEMS = 8             # 每一段最多列幾個，避免訊息太長


def fetch_repos():
    out = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", "user/repos?affiliation=owner&per_page=100"],
        check=True, capture_output=True, text=True,
    ).stdout
    return [repo for page in json.loads(out) for repo in page]


def days_since(iso):
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - then).days


def build_message(repos):
    active = [r for r in repos if r["owner"]["login"] == OWNER and not r["archived"] and not r["fork"]]

    with_issues = sorted(
        (r for r in active if r["open_issues_count"] > 0),
        key=lambda r: -r["open_issues_count"],
    )
    lo, hi = COOLING_DAYS
    cooling = sorted(
        (r for r in active if lo <= days_since(r["pushed_at"]) < hi),
        key=lambda r: days_since(r["pushed_at"]),
    )

    lines = ["🐦 啾！每週 GitHub 巡檢", ""]
    lines.append(f"📌 有 open issue/PR（{len(with_issues)}）")
    lines += [f"・{r['name']}：{r['open_issues_count']} 個" for r in with_issues[:MAX_ITEMS]] or ["・沒有，乾淨溜溜"]
    if len(with_issues) > MAX_ITEMS:
        lines.append(f"・…另外 {len(with_issues) - MAX_ITEMS} 個")

    lines += ["", f"🧊 冷掉中，{lo}～{hi} 天沒動（{len(cooling)}）"]
    lines += [f"・{r['name']}：{days_since(r['pushed_at'])} 天" for r in cooling[:MAX_ITEMS]] or ["・沒有"]
    if len(cooling) > MAX_ITEMS:
        lines.append(f"・…另外 {len(cooling) - MAX_ITEMS} 個")

    lines += ["", f"共巡了 {len(active)} 個 repo（不含 fork、封存）"]
    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv
    message = build_message(fetch_repos())
    if dry_run:
        print(message)
        return
    juju.load_env()
    juju.line_push(message)
    print("已推到 LINE")


if __name__ == "__main__":
    main()
