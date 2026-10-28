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

原始碼補充（v0.22.5，`plugins/platforms/line/adapter.py` 的 `_allowed_for_source`）：私訊檢查 `LINE_ALLOWED_USERS`，陌生人會被擋；群組與聊天室只檢查 `C`／`R` ID 本身，**不看是群裡哪個人說的**。上面第 4 節的反向測試仍要做，確認實際行為與原始碼一致。

## 2.1 權限決定（2026-10-27）

LINE 用 Hermes 預設的全套工具（含 terminal、file、browser），本人私訊與家庭群組都允許。

已知且接受的取捨：

- 家庭群組加進 `LINE_ALLOWED_GROUPS` 後，**每位成員**都能叫小鳥執行指令
- `/approve` 不檢查是誰按的（`gateway/slash_commands.py` 的 `_handle_approve_command`），群組任何人都能核准危險指令，也能用 `/yolo` 關掉確認
- 工具只能按平台設定（`platform_toolsets`），不能按人或按聊天室區分

保留的防線：

- `approvals.mode: manual`：危險指令一律停下等 `/approve`（不用預設的 `smart`，它要靠 OpenRouter 的輔助模型判斷，這裡沒有 OpenRouter）
- `LINE_HOST=127.0.0.1`：webhook 預設聽所有網路介面，改成只聽本機，經 tunnel 進來
- 不設 `LINE_ALLOW_ALL_USERS`

### 群組只在被 @ 時回應

Hermes 的 LINE adapter 沒有 `require_mention`（只有 Telegram、Signal 有），允許的群組裡每句話都會丟給模型。
本 repo 的 plugin `hermes/plugins/line-mention-gate/` 掛在 `pre_gateway_dispatch` 補上：

- 群組／聊天室：LINE 原始事件 `message.mention.mentionees[].isSelf` 為真才放行，並去掉開頭的 `@小鳥`（所以 `@小鳥啾啾 /approve` 可用）；其餘直接略過，不呼叫模型
- 私訊不受影響
- 要在 LINE 輸入框打 `@` 從名單點選小鳥；手打文字不算 mention

安裝（symlink，`hermes update` 不會蓋掉）：

```bash
ln -sfn ~/dev/juju/hermes/plugins/line-mention-gate ~/.hermes/plugins/line-mention-gate
hermes plugins enable line-mention-gate
# 重啟 gateway
```

2026-10-27 實測：群組未 @ 的兩則被略過、@ 的一則放行並回覆。

### 核准提示與硬性禁止（2026-10-28）

- `display.language: zh-hant`：核准提示改繁中；等核准時直接回「好／確認／批准／👍」即同意，「不／取消／👎」即拒絕（`gateway/run_busy.py` 的 `_route_plaintext_approval_while_busy`）。回其他話會被當成插話（`/steer`）排隊，不算核准，5 分鐘後逾時拒絕
- `approvals.deny`：43 條 fnmatch 規則（不分大小寫、會先還原 `r\m` 這類混淆），符合就直接拒絕，`/approve`、`/yolo`、`mode: off` 都放不行（`tools/approval_floors.py`）。涵蓋：
  - Documents／Desktop／Downloads／Pictures／Movies／Music／iCloud（Mobile Documents）／Library/CloudStorage 底下的 `rm`、`find -delete`（含先 `cd` 再 `rm` 的寫法）
  - `rm -r ~`、`$HOME`、`/Users`；`diskutil erase/partition/reformat`、`mkfs`、`dd of=/dev/`、`tmutil delete`
  - 讀 SSH 私鑰、`security find-*-password`／`dump-keychain`
  - `git push --force`／`-f`；`hermes config set approvals/security`（不讓小鳥自己拆防線）
  - `hermes gateway restart/stop`：小鳥在對話中重啟自己會死結（重啟要等進行中的對話結束，而那則對話在等重啟指令），2026-10-28 卡過一次、新訊息全回 `runtime_draining`，最後用 `launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway` 解開
  - 任何碰到 `.hermes/.env` 的指令：不讓小鳥用 terminal 改授權名單或讀金鑰（寫檔工具本來就擋 `.env`）。加人由本人在 Mac 上改
- 已知限制：只管 terminal 指令；小鳥的寫檔工具覆蓋檔案、`execute_code` 寫 Python 刪檔都不經過這份清單。真正的保險是備份（這台 Mac 目前**沒有** Time Machine）

考慮過但沒採用（2026-10-28）：群組裡只認本人核准的 plugin、`HERMES_WRITE_SAFE_ROOT` 限制寫檔範圍、terminal 改跑 Docker。

考慮過但沒採用：開第二個 LINE 官方帳號＋第二個 Hermes profile，家人用的小鳥只給 `web`／`memory`／`todo`／`skills`，本人專用的才能動 Mac。哪天想收緊權限，從這條路改。

## 3. 開洞（只有要對話才做）

```bash
cloudflared tunnel --url http://localhost:8646   # 正式用建議改 named tunnel，網址才固定
ngrok http 8646                                  # 開發用
```

**目前做法（2026-10-28）**：沒有網域，用 `skills/line-tunnel/` 常駐（launchd `com.joechiboo.juju.line-tunnel`）顧臨時 tunnel，斷了自動重開並用 LINE API 改 webhook URL，不用進 Console。細節見該 skill 的 `SKILL.md`。

手動做法：Tunnel 要一直開著。拿到 `https://` 網址後：
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
