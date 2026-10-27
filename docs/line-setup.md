# LINE 設定紀錄

## 帳號

- 官方帳號名稱：小鳥啾啾
- Basic ID：`@466jzkvn`（給人加好友用，agent 用不到）
- 方案：免費（每月 200 則推播，群組推播以群為單位計）
- 2026-10-27 建立，Messaging API 已啟用

> 為什麼要新建官方帳號：個人 LINE 帳號不能接 Messaging API，用個人帳號跑自動化也違反使用條款。

## agent 需要的三樣東西

都在 [LINE Developers Console](https://developers.line.biz/console/) → Provider → 小鳥啾啾：

| 項目 | 位置 | 放哪 |
|---|---|---|
| Channel secret | Basic settings | `.env` → `LINE_CHANNEL_SECRET` |
| Channel access token (long-lived) | Messaging API → Issue | `.env` → `LINE_CHANNEL_ACCESS_TOKEN` |
| 自己的 User ID（`U` 開頭） | Basic settings 最下方 Your user ID | `.env` → `LINE_OWNER_USER_ID` |

若 secret 或 token 曾經出現在任何聊天視窗或截圖裡，一律重新 Issue 一組，舊的作廢。

## 必要的開關

- Developers Console → Messaging API → **Allow bot to join group chats**：開（要進家庭群組才需要）
- OA Manager → 回應設定 → **自動回應訊息**：關（否則小鳥會先回罐頭訊息）
- OA Manager → **加入好友的歡迎訊息**：依喜好
- Webhook：單向推播不需要；要在 LINE 裡跟小鳥對話才開，屆時需要 Cloudflare Tunnel 或 ngrok 提供可被 LINE 打到的 URL

## 驗證通道（不經過 agent）

macOS / Linux：

```bash
curl -X POST https://api.line.me/v2/bot/message/push \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $LINE_CHANNEL_ACCESS_TOKEN" \
  -d "{\"to\":\"$LINE_OWNER_USER_ID\",\"messages\":[{\"type\":\"text\",\"text\":\"啾\"}]}"
```

Windows cmd 要寫成一行、全用雙引號，且訊息內容用英文（cmd 送中文會變亂碼）。

HTTP 200 並回應 `{"sentMessages":[{"id":"...",...}]}` 代表成功（早期 API 回 `{}`）；401 是 token 有誤，403 多半是尚未加小鳥為好友。

只想確認 token 屬於哪個帳號、不想真的推播時：

```bash
curl -s https://api.line.me/v2/bot/info -H "Authorization: Bearer $LINE_CHANNEL_ACCESS_TOKEN"
```

回應的 `basicId` 應為 `@466jzkvn`。

2026-10-27 首次驗證通過（推播成功、手機收到「啾」）。

## 加進群組

Group ID 只有一個來源：小鳥被拉進群時，LINE 會往 webhook 打一個 `join` 事件，`C` 開頭的那串就在裡面。所以得臨時開一次 webhook，撈到就關。

最快的做法（不用寫程式）：

1. 開 [webhook.site](https://webhook.site)，複製它給的專屬網址
2. Developers Console → Messaging API → Webhook URL 貼上 → 存檔 → 打開「Use webhook」→ Verify 應顯示 Success
3. 在 LINE 把小鳥邀進群組（Allow bot to join group chats 須已開）
4. 回 webhook.site，會收到一筆 POST，JSON 裡找 `"source": {"type": "group", "groupId": "C..."}`，整串放進 `.env` → `LINE_FAMILY_GROUP_ID`
5. 立刻回 Console 關掉「Use webhook」

提醒：

- 步驟 2 到 5 之間，群裡的訊息也會進 webhook.site，動作要連貫，撈到立刻關
- webhook.site 是第三方服務；`join` 事件只含 ID、不含訊息內容，此用途可接受，正式對話的 webhook 不可這樣用
- 之後要往群裡推播，把 Push API 的 `to` 從 `U...` 換成 `C...` 即可

## 已知小事

- 在 OA Manager 換的大頭貼要幾分鐘才同步到好友端，手機重開 LINE 即可

## 接進 Hermes Agent

完整的部署、存取控制與驗證步驟見 [hermes-line.md](hermes-line.md)。

### 備註：OpenClaw（龍蝦）

另一個選項。官方 LINE plugin（`openclaw plugins install @openclaw/line`）同樣要求公開 HTTPS webhook；設定在 `channels.line`，`dmPolicy: "allowlist"` 加 `allowFrom`。參考：https://docs.openclaw.ai/channels/line
