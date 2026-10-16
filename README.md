# FastAPI 開發更新（2026-10-16）

`python run.py` 同時啟動 PHP 網站、Uvicorn API、獨立解題 worker。先安裝 requirements.txt；測試另裝 requirements-test.txt。
原生新流程：上傳照片 → 持久任務 → 查進度 → 讀取聊天室紀錄，具 upload_id 防重複、工作復原及首張照片取名。
登入、模型設定與管理員仍保留 Flask 相容層。ESP32 韌體尚未實作。

- [架構與狀態](docs/ARCHITECTURE.md)
- [API 契約](docs/API.md)
- [測試紀錄](docs/TEST_REPORT.md)
- 本機互動 API 文件：http://127.0.0.1:5000/api/docs

> Branch update 2026-10-16: mester has been deleted. Use develop for development and main for deployment. This supersedes older branch descriptions below.

# 拍題解答：PHP 網頁＋Python API

## 使用

執行 `run.bat`（或 `python run.py`），一次啟動 PHP 網站與 Python 服務。開啟 http://127.0.0.1:5000 。登入頁為 http://127.0.0.1:5000/login.php 。

網頁只能傳送照片，不提供文字訊息或提示詞輸入。支援選取、拖曳及貼上 JPG、PNG、WebP；每張 20 MiB、每次合計 120 MiB、每次最多 8 張。先登入並在「模型設定」保存 Gemini API Key，再送出照片。可從左側重新開啟對話，繼續補照片。

## 分工

- `web/index.php`：PHP 聊天室入口、頁面與 CSRF 權杖。
- `web/login.php`：PHP 登入／註冊表單、表單驗證與頁面跳轉；帳號驗證交給 Python。
- `web/bootstrap.php`：PHP 呼叫 Python API、轉送 Session Cookie、多照片與回應。
- `web/router.php`：本機 PHP 網頁路由，提供 `/api/*` 與靜態資產。
- `app/`：FastAPI v1 與 Flask 相容層負責登入驗證、SQLite、照片保存與檢查、裝置 Token、歷史紀錄、Gemini。
- JavaScript 負責瀏覽器端照片預覽、送出與顯示解答；CSS 負責版面，PHP 不取代瀏覽器的這兩項技術。

瀏覽器 → PHP → Python → Gemini。瀏覽器只連到 PHP；Python API 預設只監聽本機 5001。

## 回答格式

保留聊天室的照片訊息與回答排列。解答採參考解答卷形式：按題號顯示題目摘要，以紅色「解」標記精簡推導，接著給出答案。支援 LaTeX、分數、根號、上下標與表格。已移除原先標語、書桌首頁與自由文字提問。

排版套件與字型存於 `app/static/vendor/`，不需要在閱讀答案時連線到 CDN。

## 執行環境

Python 套件見 `requirements.txt`。本專案已備妥官方 PHP 8.5.11 獨立環境於 `.runtime/php/`，未更動原本 XAMPP。來源為 [PHP 官方 Windows 下載](https://www.php.net/downloads.php?os=windows)，下載時校驗 SHA-256。使用其他 PHP 時，設定 `PHP_BINARY`，需 PHP 8.2 以上及 curl、fileinfo 擴充。

`WEB_PORT` 預設 5000，`API_PORT` 預設 5001。PHP 單獨部署時設定 `PYTHON_API_URL` 指向 Python，Python 可用 `python api_server.py` 單獨啟動。Apache 文件根目錄設為 `web/`，啟用 mod_rewrite 與 `.htaccess`；不要將整個專案或 uploads 當成公開目錄。本機啟動器使用 PHP 開發伺服器，正式部署請另外配置正式網頁伺服器與 HTTPS。

## 資料與驗證

保留既有 SQLite 帳號與資料。API Key 由 Python 使用 Fernet 加密保存；備份資料庫時，需另行安全備份 `.credential-key`（或環境變數 `CREDENTIAL_ENCRYPTION_KEY`）。帳號 UID 改為固定 6 碼英數裝置碼，ESP32 使用 Authorization: Bearer <裝置碼>，API 依此決定帳號及照片、解答歸屬。舊長 Token 保持相容。每個來源 IP 在 60 秒內驗證失敗 10 次會收到 429；計數位於單一 Python 程序，多程序部署需共享儲存。裝置碼具有存取權，請勿公開。PHP 登入表單及瀏覽器 API 寫入均驗證 CSRF；Python 繼續檢查使用者歸屬。

`python test_system.py`：4 組後端測試，包含照片限定、帳號隔離、金鑰與 Token、上傳驗證、解題成功及失敗狀態。

`python test_php_bridge.py`：真實啟動 PHP 與 Python、使用隔離資料庫，驗證 PHP 註冊表單、登入狀態、CSRF、多照片轉送、原圖存取、歷史紀錄、登出與錯誤密碼；模型回應使用模擬資料，不消耗配額。

`previews/chat-answer.png` 等截圖使用隔離測試資料驗證排版，並非真實 Gemini 產生的回答。

## 尚待完成

尚未使用真實模型金鑰進行外部解題測試。解題仍是同步請求，沒有持久化背景佇列、取消與 request_id 去重。ESP32 韌體、裝置螢幕圖片輸出與 RGB565 實測尚未完成。

早期 `server.py` 與根目錄 `static/index.html` 為舊版，請使用新的 `run.bat`。原 Flask 首頁現導向 PHP 網頁。
# Render 部署更新

根目錄 `render.yaml`：免費網站 + 免費 Postgres，部署分支為 `main`。
完整設定、已有資料庫的連接方式及照片限制見 [deploy/RENDER.md](deploy/RENDER.md)。
本機未設定 `DATABASE_URL` 時仍使用 SQLite；雲端資料庫由 Render 注入連線。
免費 Postgres 有 30 天期限，照片目前仍使用網站臨時檔案空間。

# 固定解答格式

開發環境預設 `ENCRYPT_STORED_KEYS=0`：users.gemini_api_key 與
model_connections.api_key 明文保存；啟動時會將既有加密金鑰轉成明文。
登入密碼仍為不可逆雜湊。設為 `ENCRYPT_STORED_KEYS=1` 並重啟，
即可將上述金鑰重新加密。請保留 `.credential-key` 以便轉換舊資料。

模型設定支援命名連線、開發模式明文保存金鑰、設定歷史與切換。版本選單透過
Gemini `models.list` 查詢，篩選支援 generateContent 的 Gemini Flash/Pro
文字解題模型並排除圖片生成、音訊等專用版本。清單不代表配額或全部
輸入能力保證，實際照片解題仍受供應商權限與模型能力限制。
目前選定的連線同時用於網頁及 ESP32；原有單一金鑰仍可沿用。

Gemini 使用 JSON schema 回傳逐題資料：`number` 題號、`question` 題目、
`clarity`（clear/unclear）、`photo_indices` 照片來源、`solution` 解法、
`answer` 答案、`unclear_reason` 不清楚原因、`recapture_hint` 補拍位置。
伺服器檢查欄位與照片索引；不清楚的題目強制清空解法及答案。
新紀錄以 `answer_sheet_v1` JSON 保存，舊 Markdown 紀錄仍可顯示。
此限制固定資料格式，不能保證模型辨識及解題一定正確。

