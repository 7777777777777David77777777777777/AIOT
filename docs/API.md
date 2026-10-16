# FastAPI v1 契約

互動文件 `/api/docs`，OpenAPI `/api/openapi.json`。裝置帶 `Authorization: Bearer <UID>`；網頁沿用登入 Cookie。資源只限本人。

| 方法／路徑 | 用途 |
|---|---|
| GET /api/v1/health | 資料庫健康檢查 |
| GET /api/v1/chats?page=1&limit=10 | 會員名稱、chats{id,title,status}、has_more；limit最多20 |
| POST /api/v1/uploads | multipart upload_id、可省略的chat_id、images；新任務202，重送200 |
| GET /api/v1/tasks/{id} | task_id、chat_id、photo_number、status、attempts、error、result_status；不回答案 |
| POST /api/v1/tasks/{id}/retry | failed且未達3次可重試，202；採用目前模型設定 |
| GET /api/v1/chats/{id}/records | items、title、has_more、next_cursor |
| POST /api/v1/chats/{id}/title | JSON `{"title":"名稱"}`，1至100字，手動名稱不再自動覆寫 |

upload_id為8至64字英數、底線、連字號，建議UUID。同一次拍照重試沿用；內容不同會拒絕。
照片欄位接受photo、image、images、images[]。每次1至8張，各20MiB，照片合計120MiB。
新考試省略chat_id，追加帶原ID。回應包含 `chat_id`、`task_id`、起始`photo_number`、`status`、`replayed`。

queued → running → completed／failed。前30秒每3秒輪詢，其後每5秒；終態停止。
completed的result_status可為ready、needs_review、needs_recapture，均應再讀records。
failed需明確retry；中斷後可繼續查同task_id。running租約10分鐘，過期由worker復原，最多3次。

records：limit預設10最多20；cursor原樣使用上次next_cursor。task_id可只取某次已完成解題。
預設format=device，items包含number、photo_indices、clarity、confidence、answer、solution、answer_status、review_note。
不包含題目全文、原圖或Key；format=web另含前端所需完整題目欄位。公式僅做基本純文字轉換。
confidence為模型自評，缺少時可為null，不代表實際正確率。

JSON錯誤欄位error：400內容無效、401未登入、403來源拒絕、404不存在或非本人、409狀態衝突、413請求過大。
既有登入、模型設定、管理員及/api/history仍走Flask相容層。
