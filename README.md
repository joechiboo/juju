# 小鳥啾啾 (juju)

透過 LINE 互動的個人 agent，引擎用 Hermes Agent。這個 repo 收納它的設定、技能（skills）與排程；agent 本體跑在家裡的 Mac 上。

## 它負責什麼

小鳥是「守門員」，不是「前鋒」：只接重複、低風險、需要有人盯著的事。需要判斷的工作（寫核心程式、代替我回覆別人）不交給它。

目前規劃的任務，依優先順序：

1. **Token 用量回報** — 每天固定時間查 API 剩餘額度，推到 LINE
2. **週四 reset 提醒** — 估算本週尚未使用的額度，避免浪費
3. **GitHub repo 巡檢** — 每週列出久未更動或有 open issue 的 side project
4. **加班時數月中提醒** — 快到上限時先叫
5. **App 審核狀態通知** — 審核狀態一變就推播

原則：一次只加一個任務，跑穩一週再加下一個。

## 結構

```
juju/
├── README.md
├── docs/
│   └── line-setup.md     # LINE 官方帳號與 Messaging API 設定紀錄
├── config/               # agent 設定檔（不含任何秘密）
├── skills/               # 一個任務一個資料夾
├── .env.example          # 需要的環境變數清單，值留空
└── .gitignore
```

## 鐵律

- `.env` 永遠不進 repo。Channel secret、access token、User ID、Group ID 全部只住在 Mac 本機的 `.env`。
- 這是 public repo。任何東西 commit 前先問一句：這能被陌生人看到嗎？
- GitHub 的 Secret scanning → Push protection 保持開啟。
- clone 後先跑 `git config core.hooksPath .githooks`，啟用 pre-commit 檢查：擋 `.env`、API key、LINE ID 格式，以及本機 `.env` 裡任何實際值。GitHub 的 push protection 不認得 LINE 的 secret 和 ID，這層才擋得到。

## 部署

1. `cp .env.example .env`，填入 LINE Developers Console 拿到的值
2. 讓 Mac 不睡：系統設定 → 能源 → 接電時防止自動睡眠，或 `caffeinate -i`
3. 啟動 agent，確認小鳥能主動說一句「啾」

詳細的 LINE 端設定見 [docs/line-setup.md](docs/line-setup.md)。
