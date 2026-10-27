# Hermes Agent × LINE — 部署與驗證

整理自 Hermes 官方文件（2026-10-27 讀取）：https://hermes-agent.nousresearch.com/docs/user-guide/messaging/line
LINE 端的帳號建立、憑證取得見 [line-setup.md](line-setup.md)。

## 0. 架構一句話

LINE → 公開 HTTPS（tunnel）→ Mac 上的 Hermes gateway（預設 port 8646，路徑 `/line/webhook`）。
只推播（cron）不需要 tunnel；要在 LINE 裡跟小鳥對話才需要。

## 1. 設定

`~/.hermes/config.yaml`：

```yaml
gateway:
  platforms:
    line:
      enabled: true

# 可選：讓「慢回應按鈕」可靠觸發，抑制會吃掉 reply token 的中間訊息
display:
  interim_assistant_messages: false
  platforms:
    line:
      tool_progress: off
```

`~/.hermes/.env`（值從 juju 的 `.env` 來）：

```env
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
LINE_ALLOWED_USERS=<U...>          # 逗號分隔
LINE_ALLOWED_GROUPS=<C...>         # 家庭群組，撈到再填
LINE_HOME_CHANNEL=<U...>           # cron 與通知的預設目的地，只能一個
# LINE_PUBLIC_URL=https://<tunnel>  # 只有傳圖片／語音／影片才需要
```

至少要設一個 allowlist；`LINE_ALLOW_ALL_USERS=true` 只准開發時用。

也可以用 `hermes gateway setup` 選 LINE 走引導式設定。

## 2. 存取控制怎麼運作

文件原文的行為：

| 來源 | 行為 |
|---|---|
| 1:1 私訊（`U`） | 文件寫「回應每一則訊息」——實測時要確認 `LINE_ALLOWED_USERS` 是否真的擋得住陌生人 |
| 群組（`C`）／多人聊天室（`R`） | 只回應 allowlist 裡的 |
| 未授權來源 | log 出現 `LINE: rejecting unauthorized source`，裡面帶來源 ID——**這就是撈 Group ID 的方法** |

沒有配對／審核流程；文件也沒說被拒絕的人會不會收到回覆。

## 3. 開洞（只有要對話才做）

```bash
cloudflared tunnel --url http://localhost:8646   # 正式用建議改 named tunnel，網址才固定
ngrok http 8646                                  # 開發用
```

Tunnel 要一直開著。拿到 `https://` 網址後：
Developers Console → Messaging API → Webhook URL 填 `https://<tunnel>/line/webhook` → Verify 應得 200 → 開啟 Use webhook。

## 4. 啟動與驗證

```bash
hermes gateway
```

log 應出現 `LINE: webhook listening on ... :8646/line/webhook`。

驗證順序：

1. `curl -i https://<tunnel>/line/webhook/health` → `{"status":"ok","platform":"line"}`
2. Console 按 Verify → 200
3. 從 LINE 私訊小鳥一句 → 它要回
4. **反向測試**：請家人從自己的 LINE 加小鳥、傳一句 → 預期不回，`~/.hermes/logs/gateway.log` 出現 rejecting + 對方的 `U` ID
5. **群組**：把小鳥拉進家庭群、任何人說一句 → log 出現 rejecting + `C` ID → 填進 `LINE_ALLOWED_GROUPS` → 重啟 gateway → 再說一句，小鳥要回

五步都如預期，存取控制就確定了。

## 5. 排程推播（B 路線，不開洞也能用）

- `LINE_HOME_CHANNEL` 填自己的 `U` ID
- cron job 設 `deliver: line`，就會推到 `LINE_HOME_CHANNEL`
- 走獨立的 push-only sender，cron 與 gateway 分開 process 也能送
- 文件沒說 cron 怎麼指定群組；目前只示範 `U` ID。要往家庭群推的任務，先實測能否覆寫目的地，不行就暫時由個人收

Push 訊息是計量的（免費方案每月 200 則），reply 不計。

## 6. 疑難排解

| 症狀 | 原因／處理 |
|---|---|
| Verify 回「invalid signature」 | secret 抄錯，或 tunnel 改了 request body；先打 health endpoint |
| 群裡不回 | `LINE_ALLOWED_GROUPS` 沒有該 `C` ID，去 log 找 rejecting |
| 傳圖失敗「LINE_PUBLIC_URL must be set」 | LINE 只收 HTTPS 網址不收檔案，設 `LINE_PUBLIC_URL` |
| 「already in use by another profile」 | 另一個 Hermes profile 用同一組 token，停掉它或另開 channel |

## 7. 限制

- 單則上限 5000 字，長回覆自動切 ~4500 字一則，一次最多 5 則
- 訊息不能編輯，串流回覆會以新訊息陸續送出
- 不渲染 Markdown，連結變成 `label (url)`
- 「輸入中」指示只在 1:1 有效
