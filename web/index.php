<?php
declare(strict_types=1);
require_once __DIR__ . "/bootstrap.php";
web_session(); page_headers(); $csrf = $_SESSION["csrf"]; session_write_close();
?>
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f7f7f5">
<title>拍題解答</title>
<meta name="csrf-token" content="<?= escape_html($csrf) ?>">
<link rel="stylesheet" href="/static/vendor/katex/katex.min.css"><link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
<aside class="sidebar" id="sidebar">
<a href="/" class="brand"><span class="brand-icon">解</span> 拍題解答</a>
<button class="new-chat" id="newChat"><span>＋</span> 新對話</button>
<div class="sidebar-section">對話紀錄</div><div id="historyList" class="history-list"><p class="sidebar-empty">登入後查看紀錄</p></div>
<div class="sidebar-bottom"><a id="adminLink" class="side-action" href="/admin.php" hidden>管理員後台 <span>↗</span></a><button id="settingsBtn" class="side-action">模型設定 <span>↗</span></button><button id="deviceBtn" class="side-action">我的裝置 <span>↗</span></button><button id="accountBtn" class="account"><span class="avatar">人</span><span id="accountName">登入／註冊</span><span>⌄</span></button></div>
</aside><button class="sidebar-scrim" id="sidebarScrim" aria-label="關閉選單" hidden></button>
<div class="main-shell">
<header class="chat-header"><div class="header-title"><button id="menuBtn" class="icon-btn" aria-label="開啟選單">☰</button><h1 id="chatTitle">新對話</h1></div><div class="header-actions"><span class="photo-only"><span></span> 僅限照片</span><a class="login-link" id="loginLink" href="/login.php">登入</a><button id="newChatMobile" class="icon-btn" aria-label="新對話">＋</button></div></header>
<main id="conversation" class="conversation" aria-label="解題對話" tabindex="-1"><div class="empty-chat" id="emptyChat"><div class="empty-icon">▧</div><h2>上傳題目照片</h2><p>支援多張照片，同一次送出一起解答。</p><button id="emptyUpload" class="outline-btn">＋ 選擇照片</button></div></main>
<div class="composer-wrap"><div class="composer" id="dropZone" tabindex="0" aria-label="照片上傳區，可拖曳圖片或按 Ctrl+V 貼上"><div id="previews" class="previews"></div><div class="composer-row"><button id="attachBtn" class="attach-btn" aria-label="加入照片">＋</button><button id="choosePhotos" class="choose-photos">選擇、拖曳或貼上題目照片</button><button type="button" id="pastePhotos" class="paste-photos">貼上圖片</button><span id="photoCount" class="photo-count"></span><button id="sendBtn" class="send-btn" disabled aria-label="送出照片">↑</button></div><input type="file" id="fileInput" accept="image/jpeg,image/png,image/webp" multiple hidden></div><div class="composer-footer"><span>JPG、PNG、WebP · 最多 8 張 · 每張 8 MB</span><span>AI 解答請自行驗算</span></div></div>
</div>
<dialog id="settingsDialog"><form id="settingsForm"><div class="dialog-heading"><h2>模型設定</h2><button type="button" data-close aria-label="關閉">×</button></div><p id="keyStatus">設定 Gemini API Key。</p><label for="connectionName">設定名稱</label><input id="connectionName" maxlength="64" placeholder="例如：課堂解題用" required><label for="apiKey">Gemini API Key</label><input id="apiKey" type="password" autocomplete="off" placeholder="輸入新金鑰，留空沿用目前金鑰"><button type="button" class="outline-btn" id="loadModels">讀取可用版本</button><label for="modelVersion">模型版本</label><select id="modelVersion" required><option value="">請先讀取可用版本</option></select><p class="fineprint">清單由 Gemini 查詢，實際使用仍受配額、地區及模型能力限制。開發模式：金鑰明文保存。</p><p class="form-error" role="alert"></p><button class="primary-btn" id="saveConnection" disabled>請先讀取並選擇版本</button><h3>設定歷史紀錄</h3><div id="connectionHistory"></div></form></dialog>
<dialog id="deviceDialog"><div class="dialog-heading"><h2>我的裝置</h2><button data-close aria-label="關閉">×</button></div><div id="devices"></div><button class="primary-btn" id="createDevice">顯示固定裝置碼</button><div id="tokenResult" hidden><label for="deviceToken">帳號裝置碼（固定 6 碼）</label><textarea id="deviceToken" readonly rows="1"></textarea><p class="fineprint">在 ESP32 輸入這組 6 碼英數字，即對應此帳號。登出或重啟都不會改變，請勿分享。</p></div></dialog>
<dialog id="accountDialog"><div class="dialog-heading"><h2>帳號</h2><button data-close aria-label="關閉">×</button></div><p id="accountInfo"></p><button id="logoutBtn" class="primary-btn">登出</button></dialog>
<dialog id="imageDialog" class="image-dialog"><button data-close class="image-close" aria-label="關閉圖片">×</button><img id="fullImage" alt="題目原圖"></dialog>
<div id="toast" role="status" hidden></div>
<script src="/static/vendor/marked.min.js"></script><script src="/static/vendor/purify.min.js"></script><script src="/static/vendor/katex/katex.min.js"></script><script src="/static/vendor/katex/auto-render.min.js"></script><script src="/static/js/photo-input.js?v=1"></script><script src="/static/js/app.js?v=photo-input-3"></script>
</body></html>
