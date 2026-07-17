# Cassistant — Implementation Plan

## 概述

Cassistant 是一個 Python CLI 工具，透過 Tailscale 連接遠端 llama.cpp（OpenAI-compatible `/v1` API），為代碼庫建立結構化的 `.md` 知識庫，並以 `/init`、`/plan`、`/build` 等指令驅動 AI 輔助開發流程。

**技術棧**：Python CLI · OpenAI SDK（指向 llama.cpp `/v1`）· SHA-256 hash 校驗 · YAML 配置

---

## 專案目錄結構

```
cassistant/                        ← CLI 工具本體（可獨立安裝）
├── pyproject.toml                 ← 套件定義，entrypoint: `cass`
├── cassistant/
│   ├── __init__.py
│   ├── cli.py                     ← CLI 入口（argparse / Click）
│   ├── config.py                  ← 讀取 config.yaml，驗證設定
│   ├── client.py                  ← OpenAI-compatible LLM 封裝
│   ├── context_budget.py          ← 128k 上下文預算管理
│   ├── hasher.py                  ← SHA-256 校驗，dirty 偵測
│   ├── commands/
│   │   ├── init.py                ← /init 實現
│   │   ├── plan.py                ← /plan 實現
│   │   ├── build.py               ← /build 實現
│   │   ├── update.py              ← /update 實現
│   │   ├── rollback.py            ← /rollback 實現
│   │   └── status.py              ← /status 實現
│   ├── prompts/
│   │   ├── analyze_file.txt       ← 單文件分析 prompt 模板
│   │   ├── build_readme.txt       ← 生成 readme.md prompt 模板
│   │   ├── build_index.txt        ← 生成 index/ 三份文件的 prompt
│   │   ├── plan.txt               ← /plan 的 prompt 模板
│   │   └── build.txt              ← /build 的 prompt 模板
│   └── utils/
│       ├── printer.py             ← 美化輸出（rich 庫）
│       └── confirm.py             ← Human-in-the-loop 確認工具
└── tests/

your_project/                      ← 使用者的代碼庫
├── src/
│   └── ...
└── .cassistant/                   ← Cassistant 管理目錄（自動生成）
    ├── config.yaml
    ├── readme.md
    ├── index/
    │   ├── api_surface.md
    │   ├── dependency.md
    │   └── data_flow.md
    ├── docs/                      ← 每個源碼文件對應的 .md
    │   └── <filename>.md
    ├── snapshots/                 ← /build 前的自動備份
    │   └── <timestamp>/
    ├── last_plan.json             ← 序列化的 Plan 結論
    └── logs/
        └── build_log.md
```

---

## config.yaml 格式

```yaml
llm:
  base_url: "http://100.x.x.x:8080/v1"  # Tailscale IP + llama.cpp port
  api_key: "none"                          # llama.cpp 不需要真實 key
  model: "llama-3.1-70b"
  context_limit: 128000                    # tokens
  timeout: 120                             # seconds
  temperature: 0.2                         # 低溫以保持確定性

project:
  # 預設支援 Python, C, C++, Java 檔案
  include: ["src/**/*.py", "**/*.py", "**/*.c", "**/*.cpp", "**/*.h", "**/*.hpp", "**/*.java"]
  exclude: ["**/node_modules/**", "**/__pycache__/**", "**/tests/**", "**/.*/**", ".cassistant/**"]
  doc_dir: ".cassistant"
```

---

## 上下文預算管理（128k）

`context_budget.py` 負責所有上下文載入決策：

| 預算分配 | Token 預留 | 用途 |
|----------|------------|------|
| 系統 prompt | ~2,000 | 固定 |
| readme.md | ~3,000 | 永遠載入 |
| 相關 `.md` 文件 | 動態，最多 60,000 | 按相關性排序載入 |
| 源碼（按需）| 動態，最多 40,000 | 僅在 .md 不夠時 |
| 用戶指令 | ~1,000 | 固定 |
| 輸出預留 | ~8,000 | 固定 |

**載入策略**：按 tag 相關性分數排序，從最高分開始載入 `.md`，超過 60k 預算就停止，改為載入部分源碼（只取最相關文件的前 N 行）。

---

## 命令詳細設計

---

### `/init` — 初始化知識庫

**觸發方式**：`cass init [--force]`
*必須在專案根目錄執行*。

```
流程：
1. 讀取 config.yaml，掃描符合 include/exclude 規則的文件列表
2. 顯示文件清單，詢問用戶確認（human-in-the-loop #1）
   → "找到 23 個文件，開始建立知識庫？[y/N]"
3. 對每個文件（逐一，無跨文件上下文）：
   a. 讀取源碼
   b. 呼叫 LLM（單獨上下文）→ 生成 docs/<filename>.md
   c. 計算源碼 sha256，寫入 .md 的 YAML front-matter
   d. 顯示進度：[3/23] auth.py ✓
4. 清空上下文，載入所有 .md
5. 呼叫 LLM → 生成 index/ 三份文件（api_surface / dependency / data_flow）
6. 呼叫 LLM → 生成 readme.md（包含模組表 + tags）
7. 顯示完成摘要，列出所有生成的文件
```

**Human-in-the-loop 點**：
- 步驟 2：確認文件清單
- 步驟 7：顯示摘要，詢問是否需要人工修正 readme.md

---

### `/status` — 檢查知識庫健康狀態

**觸發方式**：`cass status`

```
流程：
1. 掃描所有納管文件，重新計算 sha256
2. 與 .md front-matter 記錄的 hash 比對
3. 輸出報告：
   ✅ 最新（18 個文件）
   ⚠️  Dirty（3 個文件）：
      - src/auth.py（上次同步：2026-07-14）
      - src/routes.py（上次同步：2026-07-13）
      - src/new_module.py（尚未建立 .md）
4. 提示用戶執行 `cass update --dirty`
```

---

### `/update` — 增量更新知識庫

**觸發方式**：`cass update [file1 file2 ...] [--dirty] [--all]`

```
模式：
  cass update src/auth.py       → 只更新指定文件
  cass update --dirty           → 自動偵測 hash 不符的文件
  cass update --all             → 全量重建（保留人工修正的 readme.md 注釋）

流程：
1. 確定要更新的文件列表
2. 顯示清單，詢問確認（human-in-the-loop）
3. 逐一重新分析，更新 docs/*.md 和 hash
4. 重新生成 index/ 三份文件
5. 重新生成 readme.md
```

---

### `/plan` — 分析問題，輸出實現方案

**觸發方式**：`cass plan "我想要加入一個用戶登入功能"`

```
流程：
1. [自動] hash 校驗，若有 dirty 文件 → 警告用戶
   → "⚠️  3 個文件的 .md 可能已過期，建議先執行 cass update --dirty。繼續？[y/N]"
2. 載入 readme.md，LLM 分析用戶需求，從模組表提取相關 tags
3. 按 tag 相關性分數，依預算順序載入相關 .md 文件
4. LLM 判斷：目前資訊是否足以回答？
   - 足夠 → 直接跳到步驟 6
   - 不夠 → 步驟 5
5. [Human-in-the-loop] 顯示「需要查看以下源碼文件」清單，詢問確認
   → "需要載入源碼以獲取更多細節：src/auth.py, src/db.py。繼續？[y/N]"
   - 確認後載入（在剩餘 token 預算內）
6. LLM 輸出：
   - 問題分析
   - 建議修改的文件列表（及原因）
   - 分步實現方案
   - 潛在影響的模組（Impact Analysis 預覽）
7. 儲存方案狀態至 `.cassistant/last_plan.json` 供 /build 使用
8. [Human-in-the-loop] "方案已生成。是否要直接執行 /build？[y/N]"
```

---

### `/build` — 執行代碼修改

**觸發方式**：`cass build "根據上面的方案，幫我實現登入功能"`
或：`cass build --from-plan`（直接讀取 `.cassistant/last_plan.json` 結論）

```
流程：
1. [自動] hash 校驗 + dirty 警告（同 /plan 步驟 1）
2. 讀取 `.cassistant/last_plan.json` 或執行新的 /plan 邏輯，確定修改範圍與方案
3. [Impact Analysis] LLM 分析：修改這些函數/文件後，哪些其他模組可能受影響？
   → 查詢 dependency.md，找出上下游依賴
4. [Human-in-the-loop #1] 顯示完整修改計畫：
   ┌─────────────────────────────────────────┐
   │ 計畫修改：                               │
   │   📝 [NEW]    src/auth.py               │
   │   📝 [MODIFY] src/routes.py             │
   │   ⚠️  [IMPACT] src/middleware.py 可能受影響│
   │                                         │
   │ 確認執行？[y/N/e（編輯計畫）]            │
   └─────────────────────────────────────────┘
5. [自動] 備份要修改的文件到 .cassistant/snapshots/<timestamp>/
6. 呼叫 LLM 輸出 diff 格式代碼與對應的 .md 變更：
   - LLM 輸出為結構化 Unified Diff 格式
7. 套用 diff 到源碼文件
8. 更新對應的 docs/*.md（含新的 sha256 hash）
9. 更新 index/ 三份文件與 readme.md
10. [Human-in-the-loop #2] 顯示 diff 摘要，詢問是否接受
    → "所有修改已完成。查看 diff 並確認？[y/rollback/skip]"
11. 生成 build_log.md 記錄（時間戳、改動摘要、snapshot 路徑）
```

---

### `/rollback` — 還原上次 build

**觸發方式**：`cass rollback [timestamp]`
無參數時：列出所有 snapshots 並讓用戶選擇

```
流程：
1. 列出 .cassistant/snapshots/ 下所有備份
2. [Human-in-the-loop] 選擇要還原到哪個時間點
3. 確認警告："此操作將覆蓋現有文件，確定？[y/N]"
4. 還原文件 + 還原對應的 .md
5. 顯示還原摘要
```

---

## `.md` 文件標準格式

```markdown
---
source_file: src/auth.py
last_hash: sha256:abc123def456...
last_synced: 2026-07-15T16:00:00+08:00
tags: [auth, jwt, session, user, password]
---

# auth.py

## 概述
本文件實現了用戶認證系統，包含 JWT 生成、session 管理等功能。

## 公開函數

### `login(username: str, password: str) → Token`
- **用途**：驗證用戶憑證並返回 JWT
- **調用示例**：`token = login("alice", "secret")`
- **拋出**：`AuthError`（憑證無效）

## 內部依賴
- `db.py` → `get_user_by_name()`
- `config.py` → `JWT_SECRET`

## 被以下模組使用
- `routes.py` — 所有需要認證的 endpoint
```

---

## 實現分階段計畫

### Phase 1 — 核心骨架（優先實現）
- [ ] `pyproject.toml` + CLI entrypoint（`cass`）
- [ ] `config.py`：讀取/驗證 config.yaml
- [ ] `client.py`：OpenAI-compatible 封裝（base_url 指向 llama.cpp）
- [ ] `hasher.py`：sha256 計算、front-matter 讀寫、dirty 偵測
- [ ] `context_budget.py`：token 計算、載入策略
- [ ] `confirm.py`：human-in-the-loop 通用確認工具
- [ ] `printer.py`：rich 美化輸出

### Phase 2 — `/init` + `/status` + `/update`
- [ ] `commands/init.py`
- [ ] `commands/status.py`
- [ ] `commands/update.py`
- [ ] 所有 prompt 模板（analyze_file / build_readme / build_index）

### Phase 3 — `/plan` + `/build`
- [ ] `commands/plan.py`（與 `last_plan.json` 狀態儲存）
- [ ] `commands/build.py`（套用 diff 格式與 snapshot）
- [ ] `commands/rollback.py`

### Phase 4 — 測試與優化
- [ ] 單元測試
- [ ] 範例專案演練
