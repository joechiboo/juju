"""LINE 群組只在被 @ 時回應。

Hermes v0.22.5 的 LINE adapter 會回應允許群組裡的每一則訊息，沒有 require_mention。
這個 plugin 掛在 pre_gateway_dispatch：群組／聊天室訊息沒 @ 到小鳥就 skip（不呼叫模型），
有 @ 就把開頭的 @小鳥 拿掉再放行，讓「@小鳥啾啾 /approve」這類指令也能被辨識。

另外兩條放行規則（2026-10-29）：
- 訊息開頭是「小鳥」「啾啾」「小鳥啾啾」（新版 LINE PC 不能 @ 官方帳號）
- 整句是 /approve、/approve session、/approve always、/deny

判斷依據是 LINE webhook 原始事件的 message.mention.mentionees[].isSelf，
adapter 會把原始事件放在 event.raw_message。
"""

import logging
import re

logger = logging.getLogger(__name__)

GROUP_CHAT_TYPES = {"group", "room"}

# 文字開頭觸發：小鳥啾啾 / 小鳥 / 啾啾（前面可有 @，後面可接空白或標點）
KEYWORD_RE = re.compile(r"^[@＠]?(小鳥啾啾|小鳥|啾啾)[\s,，:：、!！]*")

# 核准指令：/approve、/approve session、/approve always、/deny
APPROVAL_RE = re.compile(r"^/(approve|deny)(\s+(session|always))?\s*$", re.IGNORECASE)


def _platform_name(source):
    platform = getattr(source, "platform", None)
    return str(getattr(platform, "value", platform) or "").lower()


def _self_mentions(raw):
    message = (raw or {}).get("message") or {}
    mentionees = ((message.get("mention") or {}).get("mentionees")) or []
    return [m for m in mentionees if m.get("isSelf")]


def _strip_mention(text, mention):
    """拿掉 @小鳥 那一段；位置對不上時退回「去掉開頭的 @xxx」。"""
    start, length = mention.get("index"), mention.get("length")
    if isinstance(start, int) and isinstance(length, int) and text[start:start + 1] == "@":
        return (text[:start] + text[start + length:]).strip()
    return re.sub(r"^@\S+\s*", "", text).strip()


def gate(event, **kwargs):
    source = getattr(event, "source", None)
    if source is None or _platform_name(source) != "line":
        return None
    if getattr(source, "chat_type", "dm") not in GROUP_CHAT_TYPES:
        return None  # 私訊照常

    raw = getattr(event, "raw_message", None)
    mentions = _self_mentions(raw if isinstance(raw, dict) else None)
    if not mentions:
        text = (getattr(event, "text", "") or "").strip()
        # /approve、/deny 不用叫小鳥也放行（授權檢查仍由 gateway 做）
        if APPROVAL_RE.match(text):
            logger.info("line-mention-gate: approval command in %s, passing through", source.chat_type)
            return None
        # 新版 LINE PC 不能 @ 官方帳號：開頭打「小鳥」「啾啾」（可加 @）也算叫到
        m = KEYWORD_RE.match(text)
        if m:
            rest = text[m.end():].strip()
            logger.info("line-mention-gate: keyword trigger in %s, passing through", source.chat_type)
            return {"action": "rewrite", "text": rest or "（叫了小鳥，但沒有說話）"}
        return {"action": "skip", "reason": "line-group-not-mentioned"}

    text = _strip_mention(getattr(event, "text", "") or "", mentions[0])
    logger.info("line-mention-gate: mentioned in %s, passing through", source.chat_type)
    return {"action": "rewrite", "text": text or "（被 @ 了，但沒有說話）"}


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", gate)
