# FastAPI 實作測試紀錄

日期：2026-10-16；分支 develop；本機 Windows、Python 3.9、PHP 8.5.11、SQLite。

## 自動測試

執行 `python -W ignore -m unittest discover -p 'test_*.py'`，PHP_BINARY指定本機PHP。
結果：59項，58通過、1跳過（未提供真實Postgres連線）。

- test_fastapi.py：UID歸屬、清單、新考試、追加同ID、分頁與照片續號、首張取名、手動名稱保留。
- 防重複重送、內容衝突、檔案失敗回滾、會員隔離、無效登入、來源限制與請求大小。
- 排隊／執行／完成、failed明確重試、不清楚結果終態、租約回收、同聊天室序列化、嘗試上限。
- 重建API實例仍能讀到持久任務。
- test_fastapi_php.py：真正啟動PHP和Uvicorn，以登入Cookie通過PHP轉送multipart，worker解題後再讀任務、答案與舊歷史。
- 保留原先登入、模型、管理員、答案檢查、上傳等回歸測試。

模型回應以mock模擬，沒有使用會員Key付費呼叫Gemini；流程通過不代表答案正確。
復原測試模擬租約到期，尚未做實際主機斷電、多worker長時間壓力測試。

## 本機啟動

啟用前以SQLite backup保存本機資料庫。同步運行副本後，以run.py啟動PHP、Uvicorn、worker。
實際HTTP檢查PHP入口的/api/v1/health、/api/openapi.json以及登入後的聊天室清單成功。
本機資料庫原帳號保留，新增chat_metadata、solve_tasks；未上傳資料庫或照片到Git。

## 瀏覽器隔離測試

獨立暫存SQLite與測試帳號，真正PHP／Uvicorn／worker搭配模擬模型：
貼上圖片、送出、排隊顯示、完成後答案顯示、自動聊天室取名與90%模型自評均已核對。
追加照片顯示照片2，原聊天室名稱保留；手動改名後標題及側欄同步更新。
無效PNG顯示錯誤並保留待送照片；修正圖片後可再送。

## 科目分類修正

實際英文單字釋義紀錄的chat_metadata.subject為空；原提示過度限制科目必須直接可見。
已區分考卷標題與科目：標題只能抄錄，科目可依第一張題目內容分類；英文書寫的數學不因此歸英文。
生成schema要求chat_metadata，舊紀錄解析仍相容。已確認內容的一筆未分類紀錄修正為英文。
修正後重跑59項測試通過58項、跳過1項；未再次付費呼叫模型，分類改善仍待真實照片驗證。

## 未驗證範圍

真實Gemini答案品質、ESP32 C++及硬體、Docker建置、真實Postgres、Render部署與120MiB雲端壓力尚未驗證。
Flask登入／模型／管理員相容層仍存在；版本化資料遷移尚待補。此紀錄不宣稱消除幻覺。

## 公式顯示修正
答案欄漏寫數學分隔符時，前端補齊裸分數、根號與常用符號的標記；既有公式不重複包裝。6項格式案例通過，包括兩種分數、lambda、已標記公式、巢狀根號及一般文字。模型提示同步要求所有欄位公式使用數學分隔符。


## 2026-10-20 Render 首頁403修正
雲端6ae3932已建置成功、健康檢查200，但首頁回403。發現.htaccess將內部router.php轉送一併禁止。修正為僅禁止外部直接請求router.php，目錄交由DirectoryIndex index.php處理。PHP/Uvicorn整合測試1項通過，啟動腳本語法檢查通過。本機無Apache/Docker，Apache修正仍需雲端部署後驗證。


## 網頁拍照測試
node test_camera.cjs：拍攝加入JPEG與停止鏡頭、等待授權時先關閉、拒絕權限三類模擬檢查通過。app.js與camera.js語法檢查通過，PHP頁面語法檢查通過。沒有開啟使用者實際鏡頭；手機瀏覽器權限、取景和真照片上傳待部署後驗證。

