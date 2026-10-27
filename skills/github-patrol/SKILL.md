# github-patrol — 每週 GitHub repo 巡檢

列出 `joechiboo` 名下有 open issue/PR 的 repo，以及 30～180 天沒 push、正在冷掉的 side project，推一則訊息到 LINE。

## 觸發

- 手動：`python3 skills/github-patrol/run.py`
- 預覽不推播：加 `--dry-run`
- 排程：每週一次（尚未設定）

## 需要

- 本機 `gh` 已登入（`gh auth status`），用它讀 repo 清單，不另外存 GitHub token
- `.env`：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_OWNER_USER_ID`
- 不呼叫 Claude API，不花錢；每次推播佔 LINE 免費額度 1 則（每月 200 則）

## 輸出

只推給自己（`LINE_OWNER_USER_ID`），不進家庭群組。訊息會列出 private repo 的名稱，所以不要改推到群組。

## 規則

- 排除 fork 與已封存（archived）的 repo
- `open_issues_count` 包含 PR
- 超過 180 天沒動的視為已放下，不再提醒；門檻在 `run.py` 頂端的 `COOLING_DAYS`

## 失敗時

- `gh` 沒登入或網路不通：`subprocess` 報錯結束，不推播
- LINE 回 401：token 失效，到 Developers Console 重新 Issue 後更新 `.env`
- LINE 回 403：小鳥被封鎖或刪好友
