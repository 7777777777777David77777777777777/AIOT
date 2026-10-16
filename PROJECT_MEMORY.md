> Branch update 2026-10-16: mester has been deleted. Use develop for development and main for deployment. This supersedes older branch descriptions below.

# 專案記憶

更新：2026-10-16。完整約定見 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

- 使用繁體中文溝通。使用者重視解答正確性，不能只做排版或宣稱測試通過即答案正確。
- 目前 PHP + JavaScript 前端、原生 FastAPI v1 + Flask 相容後端、本機 SQLite、獨立 worker；ESP32 韌體待做。
- 開發資料先留本機。Render Postgres 設定已準備，未自動建立或移轉雲端資料。
- 所有新開發在 develop；main 用於部署，mester 已刪除。不自動更新部署分支。
- 分支實際狀態請以 git status/log 確認，不在記憶寫死最新提交。
- 固定隨機 6 碼英數 UID 用於 ESP32，網頁登入仍需密碼。管理員為既有 admin 帳號，
  權限需 AdminRole 或 ADMIN_UIDS；完整 Key 查看是使用者明確要求，且須有審計。
- 開發 Gemini Key 明文存 DB；密碼保持雜湊。不要把實際密碼、UID、Key 放入記憶或 Git。
- 模型設定要命名、版本選單、歷史與切換。confidence 是模型自評，不是真實正確率。
- 每次 8 張、每張 20 MiB、合計 120 MiB，不累計歷史。照片暫存即可，暫不接 Google Drive。
- 全站 Noto Sans TC；解答分大題、照片、獨立 (1) 題號，下方題目／解／答案左右並排。
- 沒解或不清楚仍須顯示答案欄位的狀態文字，不留成空白畫面。
- ESP32 平常計算機，觸發 AI 後輸入 UID，API 回傳會員考試清單。
- 清單第一項固定「新考試」，之後是 API 回傳既有考試名稱，最新排前。
- 新考試直接進準備拍照；舊考試先看解答，追加照片鍵進同一準備拍照模式。
- 上傳新考試不帶 chat_id，回新 chat_id；舊考試帶原 ID，回相同 chat_id。
- 回傳 task_id 查進度，完成後用 chat_id 再取紀錄，和開啟舊考試相同。
- 輪詢不可反覆觸發解題；準備 upload_id 防重複與持久任務復原，不要只用記憶體背景工作。
- 命名只根據第一張照片：清楚考卷名優先，否則台灣日期＋科目，未知則日期＋未分類。
- 後續上傳不改名，名稱相同仍依 ID 操作；這套命名已實作，chat_metadata 保存標題，網頁可手動改名。
- 裝置紀錄不含原圖與題目全文，僅照片編號、清晰度、信心、題號、答案、解、查核狀態；分頁。
- 終止工作可含需補拍／待確認結果，不讓 ESP32 無限輪詢。
- 不把已討論的規格誤稱已完成；已有 solve_tasks、upload_id 防重複與租約復原；尚無 ESP32 韌體。

## 工作目錄

本 Git checkout 為 AIOT-render。上一層是本機運行副本，修改之後若需本機展示，
須明確同步相關檔案並重啟適當服務；避免改錯副本或只更新其中一份。
本機 PHP runtime 位於上一層 .runtime/php/php.exe，可用 PHP_BINARY 指定測試。
Python 測試使用使用者已安裝 Flask 等依賴的 Python39，不是系統 python 的空環境。

## 2026-10-16 FastAPI 實作

原生路徑 /api/v1/chats、uploads、tasks/{id}、tasks/{id}/retry、chats/{id}/records、chats/{id}/title。
API 文件 /api/docs。詳見 docs/API.md、docs/TEST_REPORT.md。
run.py 同時啟動 PHP、Uvicorn、worker；Flask 登入／模型／管理員等相容層仍保留，並未全部移除 Flask。
任務租約10分鐘、最多3次，提交結果需核對租約；可防重複入庫，無法保證供應商呼叫恰好一次。
啟動 create_all 增加新表，沒有版本化遷移工具。裝置純文字公式轉換有限。
59項測試58通過、1真實Postgres跳過；模型回應使用模擬，不代表答案正確率。
實機 ESP32、真實模型品質、Docker／Render／Postgres 壓力仍待驗證。
