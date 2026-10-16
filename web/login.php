<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
web_session(); page_headers();
$mode = ($_GET['mode'] ?? '') === 'register' ? 'register' : 'login';
$error = ''; $username = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim((string)($_POST['username'] ?? ''));
    $password = (string)($_POST['password'] ?? '');
    if (!hash_equals($_SESSION['csrf'], (string)($_POST['csrf'] ?? ''))) $error = '頁面已過期，請重新送出。';
    elseif (!$username || strlen($password) < 6) $error = '請填寫使用者名稱及至少 6 字元的密碼。';
    elseif ($mode === 'register' && $password !== ($_POST['confirm_password'] ?? '')) $error = '兩次密碼不一致。';
    else {
        [$status, $headers, $body] = backend_request('/api/auth/' . $mode, 'POST', json_encode(['username'=>$username, 'password'=>$password]));
        $data = json_decode($body, true);
        if ($status === 200) {
            session_regenerate_id(true); $_SESSION['csrf'] = bin2hex(random_bytes(32)); forward_cookies($headers);
            header('Location: /index.php', true, 303); exit;
        }
        $error = $data['error'] ?? '暫時無法登入，請稍後重試。';
    }
}
$csrf = $_SESSION['csrf']; session_write_close();
?>
<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title><?= $mode === 'register' ? '註冊' : '登入' ?> · 拍題解答</title><link rel="stylesheet" href="/static/css/style.css"></head>
<body class="auth-page"><main class="auth-card"><a href="/index.php" class="brand"><span class="brand-icon">解</span>拍題解答</a><h1><?= $mode === 'register' ? '建立帳號' : '登入' ?></h1>
<form method="post" action="/login.php<?= $mode === 'register' ? '?mode=register' : '' ?>">
<input type="hidden" name="csrf" value="<?= escape_html($csrf) ?>">
<label for="username">使用者名稱</label><input id="username" name="username" autocomplete="username" maxlength="64" required value="<?= escape_html($username) ?>">
<label for="password">密碼</label><input id="password" name="password" type="password" minlength="6" maxlength="256" autocomplete="<?= $mode === 'register' ? 'new-password' : 'current-password' ?>" required>
<?php if ($mode === 'register'): ?><label for="confirm_password">確認密碼</label><input id="confirm_password" name="confirm_password" type="password" minlength="6" maxlength="256" autocomplete="new-password" required><?php endif ?>
<p class="form-error" role="alert"><?= escape_html($error) ?></p><button class="primary-btn" type="submit"><?= $mode === 'register' ? '註冊' : '登入' ?></button></form>
<a class="auth-switch" style="text-align:center" href="/login.php<?= $mode === 'register' ? '' : '?mode=register' ?>"><?= $mode === 'register' ? '已有帳號？登入' : '還沒有帳號？註冊' ?></a><a href="/index.php" class="auth-back">返回聊天室</a></main></body></html>
