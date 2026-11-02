# family-calendar — 接送表同步到家人共用的 Google 日曆

小鳥維護的接送表只有問小鳥才看得到。這支把它同步到一個專用的 Google 日曆（例如「紀家接送」），分享給家人，大家手機上直接看。

## 觸發

- 手動：接送表有異動、使用者確認後，小鳥跑 `run.py --apply`
- 預設只預覽（列出新增／更新／刪除），加 `--apply` 才寫入

## 需要

- 個人 Gmail 帳號（不要用公司帳號）
- Hermes `google-workspace` 技能完成授權，token 在 `~/.hermes/google_token.json`（只申請 calendar 權限）
- `.env`：`FAMILY_CALENDAR_ID`（日曆 ID，長得像 `xxxx@group.calendar.google.com`）
- 行程資料：`~/.hermes/notes/calendar-events.json`（本機，**不進 repo**），格式見 `events.example.json`；可用 `FAMILY_CALENDAR_EVENTS` 改路徑
- 只用標準庫；不呼叫 Claude API、不推 LINE

## 第一次設定（在 Mac 上）

1. **建專用日曆**：Google 日曆網頁版 → 左側「其他日曆」旁的 ＋ →「建立新日曆」→ 名稱「紀家接送」、時區台北
2. **分享給家人**：該日曆的「設定和共用」→「與特定使用者共用」→ 加家人的 Gmail，權限「查看所有活動詳情」（要讓家人也能改就選「變更活動」）
3. **抄日曆 ID**：同一頁往下「整合日曆」→「日曆 ID」，填進 `.env` 的 `FAMILY_CALENDAR_ID=`
4. **建 Google OAuth 用戶端**（給小鳥存取日曆用，一次性）：
   - 建專案：https://console.cloud.google.com/projectselector2/home/dashboard
   - 啟用 Google Calendar API：https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
   - OAuth 同意畫面選「外部」，把自己的 Gmail 加成測試使用者：https://console.cloud.google.com/auth/audience
   - 建憑證 → OAuth 用戶端 ID → 應用程式類型「電腦版應用程式」：https://console.cloud.google.com/apis/credentials
   - 下載 JSON 到「下載」資料夾
5. **授權**（在 LINE 跟小鳥說「JSON 下載好了，檔名是 …」，小鳥會跑下面的指令並傳授權連結）：
   ```bash
   GSETUP="python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py"
   $GSETUP --client-secret ~/Downloads/<下載的檔名>.json
   $GSETUP --auth-url --services calendar --format json   # 開連結、按同意
   $GSETUP --auth-code "<瀏覽器網址列整串網址>" --format json
   $GSETUP --check                                          # 應印 AUTHENTICATED
   ```
   按同意後瀏覽器會跳到打不開的 `http://localhost:1/...`，這是正常的，把網址列整串複製回來就好
6. **先預覽再寫入**：
   ```bash
   python3 skills/family-calendar/run.py           # 看計畫
   python3 skills/family-calendar/run.py --apply   # 確認後寫入
   ```

## 規則

- 每筆行程用 `key` 辨識，存在 Google 事件的 `extendedProperties.private.juju_key`；內容雜湊存在 `juju_hash`，沒變就不動
- 只碰帶 `juju=family-calendar` 標記的事件，家人手動加的行程不會被改或刪
- JSON 裡刪掉的行程，日曆上也會刪
- 固定週表用 `weekday`（`MO`～`SU`，可多個 `MO,TU`）變成每週重複；`from`／`until` 限定期間（例如羽球只到 12 月底）
- 單次活動用 `date`；整天活動加 `all_day: true`，跨天用 `end_date`
- 結束時間不確定時先填一小時，`note` 註明「結束時間未定」

## 限制

- 只同步「小鳥 → 日曆」單向；家人在日曆上改小鳥建的事件，下次同步會被蓋回 JSON 的版本。要改請在 LINE 跟小鳥說
- Google OAuth 用戶端在「測試」狀態時，refresh token 7 天會過期，要重新授權；把同意畫面發布成「正式版」（個人用不需審查）就不會
