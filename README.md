# 線上念佛計數器 🙏

以 Python Streamlit + Firebase Realtime Database 建置的念佛、持咒、誦經計數系統。

---

## 功能特點

- **會員前台**：誦經項目管理、大型計數按鈕、統計紀錄、會員中心
- **管理後台**：會員管理、角色權限（RBAC）、稽核紀錄
- **安全設計**：Argon2id 密碼雜湊、登入鎖定（3次/15分鐘）、session 逾時、RBAC 預設拒絕
- **計數可靠**：RTDB transaction 原子性操作、event_id 冪等去重、撤銷保留歷史
- **台灣時區**：所有日期區間以 `Asia/Taipei` 計算（本日/本週/本月依實際日曆）
- **無障礙**：字體 ≥ 20px、觸控友善、鍵盤可操作、螢幕常亮 API

---

## 目錄結構

```
streamlit_app.py              ← 主入口（SPA 路由）
modules/
  db.py                       ← Firebase RTDB 初始化、時間工具
  auth.py                     ← 登入、密碼、鎖定、session
  rbac.py                     ← RBAC 角色權限、功能樹
  recitation.py               ← 誦經項目 CRUD
  counting.py                 ← 計數、冪等去重、撤銷
  statistics.py               ← 統計查詢、日期區間
  audit.py                    ← 稽核紀錄
  ui_components.py            ← 共用 UI、CSS、螢幕常亮
pages/
  member_count.py             ← 計數頁面（含螢幕常亮）
  member_stats.py             ← 統計紀錄頁面
  member_center.py            ← 會員中心（資料、密碼、項目）
  admin_members.py            ← 後台：會員管理
  admin_roles.py              ← 後台：角色權限設定
  admin_audit.py              ← 後台：稽核紀錄
tools/
  init_superadmin.py          ← 初始化第一位最高管理者
  migrate_timestamps.py       ← 舊時間資料遷移（dry-run 支援）
  rebuild_statistics.py       ← 統計重建（dry-run 支援）
tests/
  test_core.py                ← 37 個單元測試（密碼/時區/統計）
.streamlit/
  secrets.toml.example        ← Firebase 設定範本
firebase_rules.json           ← RTDB 安全規則
requirements.txt
```

---

## Firebase Realtime Database 路徑結構

```
/users/{user_id}/
  username, display_name, password_hash
  must_change_password, is_active, role
  failed_login_count, lockout_until
  session_token, session_last_active
  created_at, created_by

/username_index/{username}          → user_id（登入反查索引）

/recitation_items/{user_id}/{item_id}/
  name, note, is_archived, created_at, updated_at

/count_events/{user_id}/{event_id}/
  item_id, delta, is_undo, undone
  undo_of_event_id, timestamp, date_str

/daily_stats/{user_id}/{item_id}/{date_str}   → 淨次數（整數）

/roles/{role_code}/
  code, display_name, is_active, created_at

/role_permissions/{role_code}/{perm_code}     → true/false

/user_roles/{user_id}/{role_code}             → true/false

/audit_logs/{push_key}/
  actor_id, action, target_type, target_id
  result, timestamp, detail

/system_settings/
  session_timeout_minutes                      → 整數（預設 30）
```

---

## 安裝與本機啟動

### 1. 建立 Python 環境

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Firebase 設定

1. 前往 [Firebase Console](https://console.firebase.google.com/) 建立或選擇專案
2. 左側選單 → **Realtime Database** → 「建立資料庫」
3. 選擇區域：**asia-southeast1**（新加坡，台灣最近）
4. 模式選「**鎖定模式**」（Locked mode）
5. 「專案設定 → 服務帳戶」→ 產生新的私密金鑰 → 下載 JSON

### 3. 設定 Firebase 安全規則

Realtime Database → 規則 → 貼入 `firebase_rules.json` 的內容 → 發布。

所有存取由 Admin SDK 在伺服器端執行，瀏覽器完全無法直接讀寫。

### 4. 設定 Secrets

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 編輯 secrets.toml，填入下載的 JSON 金鑰各欄位
# 以及 database_url（格式如 secrets.toml.example 所示）
```

**`private_key` 注意**：從 JSON 複製後，`\n` 保留為字串（不要改成真正換行），整個值用雙引號包住放在同一行。

### 5. 初始化第一位最高管理者

```bash
python tools/init_superadmin.py
```

只需執行一次。若已存在最高管理者，工具會直接結束不覆寫。

### 6. 本機啟動

```bash
streamlit run streamlit_app.py
```

---

## 部署到 Streamlit Cloud

### Step 1：推送 GitHub

確認 `.gitignore` 已包含：
```
.streamlit/secrets.toml
```

```bash
git init
git add .
git commit -m "初始部署"
git remote add origin https://github.com/你的帳號/buddha-counter.git
git push -u origin main
```

### Step 2：Streamlit Cloud 部署

1. 前往 [share.streamlit.io](https://share.streamlit.io)
2. 點「New app」→ 選擇 repo
3. **Main file path**：`streamlit_app.py`
4. 點「Advanced settings...」→「Secrets」
5. 貼入 `secrets.toml.example` 的格式並填入真實值
6. 點「Deploy」

### Step 3：初始化管理者（Streamlit Cloud）

Streamlit Cloud 無法直接執行 terminal，在本機（已設定好 `secrets.toml`）執行：

```bash
python tools/init_superadmin.py
```

工具直接寫入 RTDB，Streamlit Cloud 上的 App 即可登入後台。

---

## 角色與預設權限

| 角色 | 說明 | 主要權限 |
|---|---|---|
| `member` | 一般會員 | 管理自己的項目、計數、統計、個人資料 |
| `account_admin` | 帳號管理者 | 新增/修改/停用會員、重設密碼（不含查看念誦紀錄） |
| `superadmin` | 最高管理者 | 所有功能，含角色權限管理、稽核紀錄、系統設定 |

---

## 密碼規則

- 至少 10 碼，須含大寫英文、小寫英文、數字
- 使用 Argon2id 雜湊儲存，絕不明文
- 管理者建立帳號或重設密碼，自動產生 10 碼臨時密碼（`secrets` 模組）
- 臨時密碼僅顯示一次，不寫入日誌或稽核紀錄
- 登入錯誤 3 次 → 鎖定 15 分鐘（儲存於 RTDB，重啟不失效）
- 首次登入強制修改密碼，未改完不能使用其他功能

---

## 工具說明

### 統計重建

若 `daily_stats` 與 `count_events` 不一致時使用：

```bash
# 先預覽
python tools/rebuild_statistics.py --dry-run

# 確認後實際執行
python tools/rebuild_statistics.py

# 只重建特定使用者
python tools/rebuild_statistics.py --user-id <user_id>
```

### 舊時間資料遷移

將無時區舊 ISO 字串加上 `+08:00`：

```bash
python tools/migrate_timestamps.py --dry-run
python tools/migrate_timestamps.py
```

### 單元測試

```bash
pip install pytest argon2-cffi
python -m pytest tests/ -v
```

---

## 備份與還原

### 備份

Firebase Console → Realtime Database → 右上角「⋮」→「匯出 JSON」

或使用 Firebase CLI：
```bash
firebase database:get / > backup-$(date +%Y%m%d).json
```

### 還原

```bash
firebase database:set / backup-20241101.json
```

---

## 常見錯誤排查

| 問題 | 原因 | 解法 |
|---|---|---|
| `ValueError: Invalid private key` | `private_key` 的 `\n` 格式錯誤 | 確認整個 key 在同一行，`\n` 為字串 |
| `NOT_FOUND: Project not found` | `project_id` 或 `database_url` 錯誤 | 從 Firebase Console 複製正確值 |
| `Permission denied` | RTDB 安全規則未設定 | 貼入 `firebase_rules.json` 並發布 |
| 登入後馬上被登出 | session_token 寫入失敗 | 確認 RTDB 可讀寫（Admin SDK 不受安全規則限制） |
| 統計顯示 0 | `daily_stats` 路徑錯誤或未重建 | 執行 `rebuild_statistics.py --dry-run` 確認 |
| 計數後沒更新 | 頁面自動 rerun 問題 | 正常現象，Streamlit 會在下一次互動後更新 |

---

## 驗收清單

| 項目 | 狀態 |
|---|---|
| 首次登入強制修改密碼 | ✓ 實作 |
| 密碼複雜度前後端驗證 | ✓ 實作（單元測試通過） |
| 登入錯誤 3 次鎖定 15 分鐘（RTDB 持久化） | ✓ 實作 |
| 臨時密碼 10 碼含三類字元（`secrets` 模組） | ✓ 實作（200 次測試通過） |
| Argon2id 雜湊，無明文儲存 | ✓ 實作 |
| 跨會員資料隔離（路徑含 user_id） | ✓ 實作 |
| 計數 event_id 冪等（重送不重複計） | ✓ 實作 |
| RTDB transaction 多裝置安全 | ✓ 實作（daily_stats atomic update） |
| 撤銷只生效一次，原始歷史保留 | ✓ 實作（undone 旗標） |
| 台灣時區日曆計算（本日/本週/本月） | ✓ 實作（單元測試通過） |
| 閏年 2 月 29 日正確處理 | ✓ 單元測試通過 |
| 舊 ISO 無時區資料相容 | ✓ 實作（parse_timestamp） |
| 封存項目歷史保留 | ✓ 實作 |
| RBAC 預設拒絕 | ✓ 實作 |
| 螢幕常亮 API（顯示實際狀態） | ✓ 實作 |
| 稽核紀錄不含密碼/雜湊 | ✓ 實作（safe_detail 過濾） |
| 360px 手機 CSS 不破版 | ✓ CSS 實作（**未在實機驗證**） |
| 連續 100 次計數正確 | **未驗證**（需連線 RTDB 整合測試） |
| 兩裝置同時計數不遺失 | **未驗證**（RTDB transaction 設計支援） |
