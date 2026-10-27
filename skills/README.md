# Skills

一個任務一個資料夾，裡面至少有一個 `SKILL.md` 說明：

- 觸發方式（排程 cron、事件、或手動）
- 需要哪些環境變數
- 輸出到哪（LINE 個人、家庭群組、或只寫 log）
- 失敗時怎麼辦

第一個上線的是 `github-patrol/`：每週巡檢 GitHub repo。跑穩一週再加第二個。

原本排第一的 `token-report/`（查 API 剩餘額度）往後延：查用量要 Admin API key，個人帳號（Individual Org）不能建，得先把帳號升級成組織。

共用的讀 `.env`、推 LINE 放在 `lib/juju.py`，只用 Python 標準庫，不用裝套件。
