"""小鳥啾啾的共用工具：讀 .env、推 LINE。只用標準庫。"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINE_TEXT_LIMIT = 5000  # LINE 單則文字訊息上限


def load_env(path=ROOT / ".env"):
    """把 .env 讀進 os.environ（已存在的環境變數優先）。"""
    if not path.exists():
        raise SystemExit(f"找不到 {path}，先 cp .env.example .env 再填值")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f".env 缺少 {name}")
    return value


def line_push(text, to=None):
    """推一則文字訊息。預設推給自己（LINE_OWNER_USER_ID）。"""
    token = require("LINE_CHANNEL_ACCESS_TOKEN")
    to = to or require("LINE_OWNER_USER_ID")
    if len(text) > LINE_TEXT_LIMIT:
        text = text[: LINE_TEXT_LIMIT - 20] + "\n…（訊息過長已截斷）"
    body = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        # 只回報狀態碼與 LINE 的錯誤訊息，不印 token
        detail = e.read().decode(errors="replace")[:300]
        raise SystemExit(f"LINE 推播失敗 HTTP {e.code}: {detail}")
