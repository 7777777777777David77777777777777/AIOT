> Branch update 2026-10-16: mester has been deleted. Use develop for development and main for deployment. This supersedes older branch descriptions below.

# AIOT 拍題計算機：完整架構與開發規格

更新：2026-10-16（Asia/Taipei）

本文是需求與實作交接基準。標示「規劃」的項目尚未完成，不得對外宣稱已可用。

## 1. 系統目標

ESP32 平常為一般計算機。觸發指定操作後進入 AI 模式，以固定 6 碼 UID
辨識會員，選擇考試、拍攝題目、取得解答。PHP 網站提供相同紀錄、模型設定
及管理員後台。核心目標是可靠解題；不能把流程通過、模型高信心等同答案正確。

## 2. 已有系統與目標架構

目前實際執行：

```text
瀏覽器 HTML/CSS/JavaScript
  → PHP 頁面及 API 轉送（本機 5000）
  → Python Flask API（本機 127.0.0.1:5001）
      ├─ 本機 SQLite：exam_solver.db
      ├─ uploads/ 原始照片
      └─ Gemini generateContent
```

目標架構（FastAPI、工作程序、ESP32 韌體尚待實作）：

```text
瀏覽器 → PHP → FastAPI ───────────┐
ESP32（C++、Game Boy 風格）→ FastAPI │
                                ├─ SQLAlchemy → 本機 SQLite／部署用 Postgres
                                ├─ 照片儲存
                                └─ 持久任務 → 工作程序 → Gemini → 答案檢查
```

PHP 保留頁面、登入表單、Session/CSRF 與 API 轉送；JavaScript 處理瀏覽器互動與排版。
Python 負責登入驗證、UID 對應、資料、照片、模型呼叫及解答檢查。
Gemini API Key 不送到 ESP32。FastAPI 遷移不代表解題品質會自動提升。

## 3. 會員、模型與管理員

- 每位會員具有唯一、隨機且固定的 6 碼英數 UID；登出或正常重啟不更換。
- ESP32 以 `Authorization: Bearer <UID>` 呼叫裝置 API。
- UID 對應帳號，API 自行判定紀錄歸屬，不接受裝置任意指定會員 ID。
- 網站會員使用密碼登入與 Session；一般會員只能查看自己的資料。
- 6 碼 UID 是目前約定的裝置憑證，要避免外洩，並保留錯誤嘗試限制。
- 網頁可建立命名模型設定、讀取 Gemini 版本清單、保存歷史與切換使用中設定。
- 開發模式 Gemini 金鑰明文保存（`ENCRYPT_STORED_KEYS=0`），密碼仍為雜湊。
- 管理員帳號指定為 `admin`，但程式不能因名稱叫 admin 就自動給權限。
- 本機透過 `admin_roles` 授權；雲端可用 `ADMIN_UIDS` 指定既有帳號。
- `/admin.php` 查看所有會員、照片、解題紀錄、JSON、模型設定歷史。
- 管理員可以按鈕查看完整 API Key；每次查看記錄於 `admin_audit`。
- 裝置 UID 不能取代管理員 Session 進入管理 API。

## 4. ESP32 畫面與操作（已確認需求，尚未實作韌體）

裝置使用 C++，風格類似 Game Boy。啟動 AI 的實際按鍵組合、硬體與顯示器規格待定。

```text
開機 → 一般計算機 → 使用者觸發 AI → 輸入 UID
 → 呼叫 API 驗證並取得考試清單

選擇考試
  ▶ 新考試                 （固定第一項，ESP32 自行顯示）
    電工原理第一次段考      （API 回傳的既有紀錄）
    2026-10-16 電工原理
```

- 既有紀錄最新排前面；以 ID 操作，不以標題作為識別。
- 選「新考試」直接進入準備拍照模式，尚不建立空紀錄。
- 選「舊考試」先請求並顯示答案紀錄。
- 在舊考試按追加照片鍵，同樣進入準備拍照模式。
- 新考試與追加照片使用同一套相機流程；差別只有目前是否有 chat_id。
- 準備拍照 → 拍攝 → 確認／重拍 → API 上傳。實體鍵映射仍待硬體確認。
- 新考試取消回清單，不留下空紀錄；追加取消回原本答案畫面。

## 5. 新考試與追加照片的 API 流程（規劃）

```text
拍攝、確認
 → 上傳照片
 → API 保存照片及工作，回應 chat_id、task_id、photo_number
 → ESP32 保存 chat_id 和 task_id
 → 定時查詢 task_id
 → 完成：停止輪詢
 → 用 chat_id 呼叫聊天室紀錄 API
 → 顯示本次新增照片的答案
```

新考試：不帶 chat_id，後端建立考試並回傳新的 chat_id。
追加照片：帶既有 chat_id，後端驗證歸屬並回傳相同 chat_id。
上傳失敗不覆蓋 ESP32 原有的 chat_id。照片編號在同一考試內持續累加。

```json
{
  "chat_id": "exam-id",
  "photo_number": 3,
  "task_id": "task-id",
  "status": "queued"
}
```

chat_id 是整場考試 ID；task_id 是本次解題工作 ID。每次上傳可有新的 task_id。
task_id 只查進度；答案一律由聊天室紀錄 API 取得，新舊紀錄共用同一路徑。
API 的實際路徑與錯誤格式在 FastAPI 實作前固定；上面欄位是已確認的流程需求。

## 6. 輪詢、失敗與重試（規劃）

- 每 3 秒查詢一次；超過 30 秒改每 5 秒，網路失敗再延長間隔。
- 查狀態不重新上傳，不再次呼叫 Gemini。
- 完成或失敗就停止輪詢；離開等待畫面可暫停，返回時接續。
- 等待時仍能處理按鍵與查看舊答案。
- 每次拍攝建立 upload_id，重試沿用，後端以會員＋upload_id 防重複。
- ESP32 保存未完成的 chat_id、task_id、upload_id，斷線或重開機後接續。
- 工作必須寫入資料庫，不能只靠記憶體或 FastAPI BackgroundTasks 保證完成。
- 工作至少有 queued、running、completed、failed；額外辨識／查核階段只在真的拆分後顯示。
- 「答案待確認／照片需補拍」是解題結果，不代表工作仍在執行；應為終止輪詢的狀態。
- 持久任務的領取、重啟復原、逾時、重試及多程序鎖定仍待設計實作。

## 7. 聊天室命名（規劃）

第一張照片辨識完成後，僅自動命名一次：

1. 考卷名稱清楚可辨：直接用，例如「電工原理第一次段考」。
2. 沒有考卷名但可判斷科目：台灣日期＋科目，例如「2026-10-16 電工原理」。
3. 無法判斷科目：「2026-10-16 未分類」，不可自行猜名稱。

先回傳 ID，命名可隨第一張照片解題完成後更新。後續照片不自動改名。
規劃將 title 獨立於 prompt，網頁提供手動改名。
目前程式仍用第一題內容覆寫 QuestionBatch.prompt，不代表此命名規則已完成。

## 8. ESP32 紀錄回應（規劃）

裝置只需要照片編號、照片清晰度、模型自評信心、原題號、答案、解說與查核狀態。
不用下載原照片，不需題目全文；分頁讀取，不一次載入所有解答。

```json
{
  "chat_id": "exam-id",
  "items": [{
    "photo_indices": [1],
    "clarity": "clear",
    "confidence": 98,
    "number": "1",
    "answer": "B：6 V",
    "solution": "電位差＝功÷電量，18÷3＝6 V",
    "answer_status": "unverified"
  }],
  "has_more": false
}
```

```text
照片 1
照片清楚 · 答案信心：98%
(1) 答案
B：6 V
解
電位差＝功÷電量，18÷3＝6 V
```

需要另產生適合小螢幕的純文字公式；目前網站保存的 LaTeX 不能直接假設 ESP32 可渲染。
沒有答案或照片不清楚，也要有答案欄位的顯示文字，例如「待確認」「無法作答：照片不清楚」。
裝置介面不得因 confidence 高，就隱藏 needs_review 提示。

## 9. 現有解答格式與品質限制

- 每題 JSON 包含 number、question、clarity、photo_indices、solution、answer、
  confidence、unclear_reason、recapture_hint，以及伺服器 answer_status、review_note。
- confidence 是模型自行回報的 0～100 整數，與正確率無法直接等同；舊紀錄缺少則未提供。
- 不限制模型進行分析，但輸出應是可檢驗的簡明解法，不能用猜測裝成標準答案。
- 已有保守文字規則檢查猜測、缺漏原文與矛盾，未建立真正外部事實查證系統。
- 字數題會程式計算候選引文的漢字數，但無法因此證明引文及默寫範圍正確。
- 目前字數題採保守待確認；這不是已完成「原文來源查證」。
- 前面的國文、法規測試已發現錯字、漏題、混題、錯誤引文與條號；不能宣稱已杜絕幻覺。
- 測試通過主要代表程式流程正確，不能宣稱題庫答對率。

## 10. 網站排版與照片限制（已實作）

- 網站只接受照片提問，不提供文字聊天輸入。
- 全站 Noto Sans TC，搭配系統繁中字型備援。
- 大題標題 → 照片來源 → 獨立題號 (1)，下方「題目／解／答案」左右並排。
- 「解」保留玫紅色塊，答案粗體與分隔線。
- 清晰度＋答案信心徽章；查核狀態與自評分數分開。
- 每張最多 20 MiB、每次最多 8 張、每次照片合計 120 MiB，不累計先前照片額度。
- PHP/Flask 請求上限 128 MiB 預留 multipart 空間；PHP 用暫存檔串流轉送。
- 原圖保存；模型副本長邊最多 3200 像素，另限制 JPEG 大小。
- 2500 萬像素防護仍存在，不是所有小於 20 MiB 的巨大解析度影像都接受。
- 同一對話新照片接續編號；解題不把歷史所有原圖反覆送出。
- 120 MiB 在 Render 免費主機的記憶體、逾時與並發行為尚待實測。

## 11. 資料庫與現有檔案

目前資料表：users、devices、question_batches、photos、messages、
model_connections、admin_roles、admin_audit。

- question_batches 是目前聊天室／考試容器，id 為目前 batch_id。
- photos 保存檔案路徑與歸屬；messages 保存對話及答案。
- messages.content 的 model 訊息保存 answer_sheet_v1 JSON，不是每次另寫 JSON 檔。
- Gemini 原始回應目前未自動持久化；debug/latest_saved_answer.json 是手動匯出的快照。
- FastAPI 需新增獨立 tasks、upload_id 等資料模型及遷移；尚未完成。
- 現有 /api/tasks/<task_id>/status 參數實際查的是 QuestionBatch ID，
  不能當作已有獨立任務表；需在遷移時處理相容性。

## 12. 開發與部署

- 開發資料先留本機 SQLite，不把本機會員與照片自動搬雲端。
- Render Docker/Apache/Gunicorn 與 Postgres Blueprint 已準備；不等於已上線。
- 雲端 Postgres 由 DATABASE_URL 注入；RENDER=true 時缺少連線會拒絕臨時 SQLite fallback。
- Render 免費 Postgres 30 天期限（2026-10-16 查證），建立前再確認官方規定。
- 網站臨時檔案可能在休眠／重啟／部署後消失。使用者已決定暫不接 Google Drive，
  照片僅供檢查，接受其暫存性；帳號與答案由 Postgres 保存。
- FastAPI 開發先在本機，尚未遷移 Flask；獨立工作程序亦尚未實作。
- 程式儲存庫：https://github.com/7777777777777David77777777777777/AIOT
- develop 為開發分支；mester 為既有部署分支（名稱確實是 mester）；main 保留。
- 最新已推送 develop：2947664。mester 尚未包含全部近期開發改動。
- 不因更新文件而自動合併或推送 mester；發布須依使用者當次授權。

## 13. 下一步順序

1. 固定裝置 API 路徑、請求／回應、分頁、錯誤碼與狀態表。
2. 設計 chat title、獨立 task、upload_id 與資料庫遷移。
3. 在 develop 建立 FastAPI，先沿用本機 SQLite 並與 PHP 做相容測試。
4. 實作 UID → 考試清單 → 上傳 → 查工作 → 讀紀錄的整套整合測試。
5. 加入可恢復工作程序、防重複上傳、斷線及重啟測試。
6. 再接 ESP32 C++ 狀態機與 Game Boy 介面，最後驗證實機照片與顯示。
7. 解題品質建立有標準答案的測試集，再逐步加入來源查證與驗算工具。
