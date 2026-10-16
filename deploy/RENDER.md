> Branch update 2026-10-16: mester has been deleted. Use develop for development and main for deployment. This supersedes older branch descriptions below.

# Render 部署

## 開發分支目前上傳設定

每張照片最多 20 MiB、每次最多 8 張、照片合計最多 120 MiB。
PHP 與 Flask 的請求上限為 128 MiB，預留 multipart 表單額外空間。
PHP 用暫存檔串流轉送；原始照片保存後，送模型的副本會縮至長邊最多
3200 像素並限制 JPEG 大小。既有 2500 萬像素影像防護仍保留。
目前僅在本機驗證跨 PHP/Python 的 9 MiB 檔案與一般流程，
120 MiB 的雲端壓力及逾時行為仍須部署後測試。

## 管理員後台

網址 `/admin.php`，可搜尋會員、查看模型設定歷史、照片、解答與 JSON。
完整 API Key 需另外按「顯示完整 API Key」，只允許管理員 Session；
每次查看記錄在 `admin_audit`，不保存金鑰值。ESP32 裝置碼不能存取管理 API。

本機已有帳號可執行 `python manage_admin.py grant admin`，撤銷用
`python manage_admin.py revoke admin`。權限保存於 `admin_roles` 表。

Render 免費方案無 Shell 時：先註冊自己的管理帳號，從「我的裝置」取得該帳號
6 碼 UID，在 Web Service 環境變數設定 `ADMIN_UIDS=該UID`，重啟服務。
仍須使用該帳號的密碼登入，知道 UID 本身無法進入後台；不要把別人的 UID 填入。
雲端權限與本機資料庫獨立，不會因本機已授權而自動變成管理員。

## 目前預設：免費網站 + Postgres

根目錄 `render.yaml` 已改為建立免費 Web Service 與免費 Postgres，兩者同在
Singapore 區域。Render 透過 `fromDatabase` 自動注入內部 `DATABASE_URL`，
程式使用 psycopg 3 連線；雲端缺少此設定時會停止啟動，避免意外使用臨時 SQLite。

1. Render → New → Blueprint，選本儲存庫與 `main` 分支，使用根目錄 `render.yaml`。
2. 確認畫面中的 Web Service 與 Postgres 都是 Free，再建立。
3. 若先前已手動建立 Postgres，請勿重複建立；手動部署 Web Service 時，
   將資料庫的 Internal Database URL 填入 Web Service 的 `DATABASE_URL`。
   資料庫與網站必須在同一區域；不要把連線字串提交 GitHub 或貼到公開紀錄。
4. 首次啟動會建立空資料表。本機 SQLite 帳號不會自動搬移，請在雲端註冊。

網站休眠或重新部署後，Postgres 內的帳號、裝置碼、模型設定及解答紀錄仍保留。
**免費 Postgres 會在建立後 30 天到期**，到期前需匯出資料或升級。
照片仍存於免費網站的臨時檔案空間，休眠／重新部署後可能消失；
舊解答文字可讀取，但原照片與使用原照片再次解題仍會受影響。
目前沒有自動搬移 SQLite 資料、照片儲存服務或自動資料庫備份。

若 Render 已有其他免費 Postgres，需使用該資料庫或調整方案，避免超過免費數量限制。
健康檢查 `/health.php` 會透過 Python 檢查資料庫是否能連線。

以下保留付費磁碟替代方案，不是根目錄 Blueprint 的預設。

本專案使用同一個 Docker Web Service 執行 Apache/PHP 與 Gunicorn/Python。
Render 對外只連 Apache 的 `$PORT`，Python 固定監聽容器內的 127.0.0.1:5001。

## 有保存需求的版本

1. 將專案程式上傳到自己的 GitHub 儲存庫。不要上傳 `.session-secret`、
   `.credential-key`、`exam_solver.db`、`uploads/`、`debug/` 或 `.env`。
   `.gitignore` 已排除這些資料；Docker 也只複製執行所需檔案。
2. 在 Render 選 New → Blueprint，連接儲存庫的 `main` 分支，檔案路徑指定 `deploy/render-persistent.yaml`。
3. 此設定包含 **付費 Web Service 與 1 GB 持久磁碟**，先確認畫面費用再建立。
4. 部署後打開 Render 提供的 HTTPS 網址 `/login.php`，重新註冊帳號。
5. 在模型設定填自己的 Gemini Key、讀取模型版本、儲存設定。
6. 上傳題目測試，登出再登入，確認紀錄可讀取；重新部署後再確認帳號和照片仍存在。

金鑰依目前開發需求維持明文（`ENCRYPT_STORED_KEYS=0`）；登入密碼仍雜湊。
若要切回加密，設 `ENCRYPT_STORED_KEYS=1` 後重啟，並保留磁碟上的 `.credential-key`。
SECRET_KEY 由 Render 產生；資料庫與照片放在 `/var/data`，不在原始碼裡。

## 免費臨時展示

根目錄 `render.yaml` 已設定 Free 並接獨立 Postgres，不含持久磁碟。
設定 `DATA_DIR=/var/data`、`COOKIE_SECURE=1`、固定且隨機的 `SECRET_KEY`，
健康檢查路徑 `/health.php`。不需要另外填 Build Command 或 Start Command。
Postgres 保存帳號與金鑰；沒有持久磁碟時，上傳照片可能在重啟、重新部署後消失。

## ESP32

API 網址換成 `https://你的服務.onrender.com/api/...`，不再使用 127.0.0.1。
ESP32 使用 HTTPS 客戶端並驗證伺服器憑證，帶入雲端帳號的固定裝置碼：
`Authorization: Bearer 六碼裝置碼`。新註冊的雲端帳號與本機測試帳號不同。

## 現有本機資料

預設不移轉，雲端會從空資料庫開始。若需搬移，必須一起搬資料庫、照片與必要密鑰，
並修正 photos.file_path 的 Windows 絕對路徑成容器的 `/var/data/uploads/...`。
不能只把 SQLite 檔案複製過去；請勿將這些資料放入公開 Git 儲存庫。

## 本機容器驗證（需 Docker）

```text
docker build -t photo-exam-solver .
docker run --rm -p 10000:10000 -e COOKIE_SECURE=0 -v photo-data:/var/data photo-exam-solver
```

瀏覽 `http://localhost:10000/health.php` 應回傳 `{"ok":true}`。
再測試註冊、登入、模型設定、照片解題與停止後重新啟動的資料保存。
容器內只啟動一個 Gunicorn worker，讓目前裝置碼錯誤次數限制維持一致。

## 分支

`develop` 用於開發，驗證後合併至 `main`；Render 使用 `main`。
`main` 保留初始版本。分支名稱依目前專案約定為 `main`。

參考：
- https://render.com/docs/docker
- https://render.com/docs/disks
- https://render.com/docs/free
