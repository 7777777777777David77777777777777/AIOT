<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
[$status, $headers, $body] = backend_request('/api/auth/me');
$me = json_decode($body, true);
if (empty($me['authenticated'])) { header('Location: /login.php'); exit; }
if (empty($me['user']['is_admin'])) { http_response_code(403); echo '只有管理員可以查看此頁面'; exit; }
web_session(); page_headers();
?>
<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="csrf-token" content="<?= escape_html($_SESSION['csrf']) ?>"><title>管理員後台 · 拍題解答</title><link rel="stylesheet" href="/static/css/admin.css"></head>
<body><header><div><span class="eyebrow">拍題解答</span><h1>管理員後台</h1></div><a href="/index.php">返回聊天室 ↗</a></header>
<main><section class="members"><h2>會員</h2><form id="searchForm"><input id="search" placeholder="搜尋會員帳號" aria-label="搜尋會員帳號"><button>搜尋</button></form><p id="memberCount"></p><div id="memberList"></div><nav><button id="previousMembers">上一頁</button><span id="membersPage"></span><button id="nextMembers">下一頁</button></nav></section>
<section id="memberDetail" class="detail"><p class="muted">選擇左側會員，查看模型設定與解題紀錄。</p></section></main>
<p id="adminError" role="alert"></p><dialog id="keysDialog"><div class="dialog-top"><h2>會員 API Key</h2><button id="closeKeys" aria-label="關閉金鑰">×</button></div><p>僅供管理員檢查；本次查看已留存紀錄。</p><div id="keyList"></div></dialog>
<script src="/static/js/admin.js?v=1"></script></body></html>
