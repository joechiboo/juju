# line-tunnel — 讓 LINE 一直連得到小鳥

LINE 要透過公開 HTTPS 才找得到 Mac 上的 Hermes gateway。沒有自己的網域，只能用 cloudflared 臨時 tunnel（trycloudflare），它每次啟動網址都不同、網路一斷就作廢。這支常駐負責把它接回來。

## 觸發

- 常駐：launchd `KeepAlive`（`config/launchd/com.joechiboo.juju.line-tunnel.plist`），開機登入就跑，程式掛了 30 秒內重開
- 看狀態：`tail -f logs/line-tunnel.log`

## 需要

- `cloudflared`（`brew install cloudflared`）
- `.env`：`LINE_CHANNEL_ACCESS_TOKEN`
- Hermes gateway 在 `127.0.0.1:8646`
- 不呼叫 Claude API、不推播（不吃 LINE 免費額度）

## 規則

- 開 tunnel → 等外網 health 通 → `PUT /v2/bot/channel/webhook/endpoint` 改 LINE webhook，再 `GET` 確認
- 每 60 秒從外網打一次 `/line/webhook/health`；連續 3 次失敗或 cloudflared 結束就重開、換網址
- gateway 本機 health 不通時不動 tunnel（gateway 由 `ai.hermes.gateway` 負責重啟）
- 起不來時重試間隔從 5 秒倍增到最多 5 分鐘

## 限制

- 斷線到偵測、重開大約 3～4 分鐘，這段時間傳給小鳥的訊息要靠 LINE 的 Webhook redelivery
- Mac 睡著時什麼都不會跑；醒來後第一輪檢查就會接回
- 有 Cloudflare 網域後應改用 named tunnel（網址固定，不必改 webhook），這支就可以退役
