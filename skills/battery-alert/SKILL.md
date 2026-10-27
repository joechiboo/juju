# battery-alert — Mac 電量提醒

小鳥跑在 Mac 上，Mac 沒電小鳥就睡著了。用電池且電量降到 20%、10% 時各推一則 LINE。

## 觸發

- 排程：launchd 每 5 分鐘（`config/launchd/com.joechiboo.juju.battery-alert.plist`）
- 手動檢查：`python3 skills/battery-alert/run.py --dry-run`

## 需要

- `pmset`（macOS 內建）
- `.env`：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_OWNER_USER_ID`
- 不呼叫 Claude API；每輪放電最多推 2 則

## 輸出

只推給自己。

## 規則

- 只在「用電池且放電中」時提醒；接電就清掉紀錄，下一輪放電重新提醒
- 已提醒過的門檻記在 `data/battery-alert.json`（不進 repo）
- 一次跳過兩個門檻（例如睡醒時已 8%）只推一則
- 門檻在 `run.py` 頂端的 `THRESHOLDS`

## 限制

Mac 睡著時 launchd 不會跑，醒來才補檢查。用電池時系統預設很快就睡，所以這個提醒只在 Mac 醒著時有效。
