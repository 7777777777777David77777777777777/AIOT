# Render 部署

本專案使用同一個 Docker Web Service 執行 Apache/PHP 與 Gunicorn/Python。
Render 對外只連 Apache 的 `$PORT`，Python 固定監聽容器內的 127.0.0.1:5001。

## 有保存需求的版本

1. 將專案程式上傳到自己的 GitHub 儲存庫。不要上傳 `.session-secret`、
   `.credential-key`、`exam_solver.db`、`uploads/`、`debug/` 或 `.env`。
   `.gitignore` 已排除這些資料；Docker 也只複製執行所需檔案。
2. 在 Render 選 New → Blueprint，連接儲存庫的 `mester` 分支，檔案路徑指定 `deploy/render-persistent.yaml`。
3. 此設定包含 **付費 Web Service 與 1 GB 持久磁碟**，先確認畫面費用再建立。
4. 部署後打開 Render 提供的 HTTPS 網址 `/login.php`，重新註冊帳號。
5. 在模型設定填自己的 Gemini Key、讀取模型版本、儲存設定。
6. 上傳題目測試，登出再登入，確認紀錄可讀取；重新部署後再確認帳號和照片仍存在。

金鑰依目前開發需求維持明文（`ENCRYPT_STORED_KEYS=0`）；登入密碼仍雜湊。
若要切回加密，設 `ENCRYPT_STORED_KEYS=1` 後重啟，並保留磁碟上的 `.credential-key`。
SECRET_KEY 由 Render 產生；資料庫與照片放在 `/var/data`，不在原始碼裡。

## 免費臨時展示

根目錄 `render.yaml` 已設定 Free，沒有持久磁碟。Blueprint 選 `mester` 分支即可。
也可以手動新增 Docker Web Service，選 Free。
設定 `DATA_DIR=/var/data`、`COOKIE_SECURE=1`、固定且隨機的 `SECRET_KEY`，
健康檢查路徑 `/health.php`。不需要另外填 Build Command 或 Start Command。
沒有持久磁碟時，帳號、照片和金鑰可能在重啟、重新部署後消失，不能當正式資料保存。

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

`develop` 用於開發，驗證後合併至 `mester`；Render 使用 `mester`。
`main` 保留初始版本。分支名稱依目前專案約定為 `mester`。

參考：
- https://render.com/docs/docker
- https://render.com/docs/disks
- https://render.com/docs/free
