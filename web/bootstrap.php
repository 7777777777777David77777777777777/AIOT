<?php
// PHP owns page flow. Authentication, persistence, and AI calls stay in Python.
declare(strict_types=1);
const MAX_UPLOAD_BYTES = 32 * 1024 * 1024;
function escape_html(string $value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function web_session(): void {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_name('photo_web_session');
        session_set_cookie_params(['httponly' => true, 'samesite' => 'Lax', 'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off']);
        session_start();
    }
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
}
function page_headers(): void {
    header('Cache-Control: no-store'); header('X-Content-Type-Options: nosniff'); header('X-Frame-Options: DENY');
    header('Content-Type: text/html; charset=utf-8');
}
function backend_request(string $path, string $method = 'GET', string $body = '', string $contentType = 'application/json'): array {
    $base = rtrim(getenv('PYTHON_API_URL') ?: 'http://127.0.0.1:5001', '/');
    $curl = curl_init($base . $path);
    $headers = ['Accept: application/json', 'Host: ' . ($_SERVER['HTTP_HOST'] ?? '127.0.0.1')];
    $headers[] = 'X-Forwarded-Proto: ' . ((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http');
    if (!empty($_SERVER['HTTP_COOKIE'])) $headers[] = 'Cookie: ' . $_SERVER['HTTP_COOKIE'];
    foreach (['HTTP_AUTHORIZATION' => 'Authorization', 'HTTP_X_API_KEY' => 'X-API-Key', 'HTTP_ORIGIN' => 'Origin'] as $key => $name) {
        if (!empty($_SERVER[$key])) $headers[] = $name . ': ' . $_SERVER[$key];
    }
    if ($method !== 'GET') $headers[] = 'Content-Type: ' . $contentType;
    $responseHeaders = [];
    curl_setopt_array($curl, [CURLOPT_RETURNTRANSFER => true, CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_HTTPHEADER => $headers, CURLOPT_CONNECTTIMEOUT => 5, CURLOPT_TIMEOUT => 100,
        CURLOPT_PROXY => '', CURLOPT_FOLLOWLOCATION => false,
        CURLOPT_HEADERFUNCTION => function ($curl, string $line) use (&$responseHeaders): int {
            $parts = explode(':', $line, 2);
            if (count($parts) === 2) $responseHeaders[strtolower(trim($parts[0]))][] = trim($parts[1]);
            return strlen($line);
        }]);
    if ($method !== 'GET') curl_setopt($curl, CURLOPT_POSTFIELDS, $body);
    $result = curl_exec($curl); $status = (int)curl_getinfo($curl, CURLINFO_HTTP_CODE);
    curl_close($curl);
    if ($result === false || !$status) return [502, ['content-type' => ['application/json']], json_encode(['error' => 'Python 後端未連線，請使用 run.bat 啟動整套系統。'], JSON_UNESCAPED_UNICODE)];
    return [$status, $responseHeaders, $result];
}
function forward_cookies(array $headers): void {
    foreach ($headers['set-cookie'] ?? [] as $cookie) header('Set-Cookie: ' . $cookie, false);
}
function json_error(string $message, int $status): never {
    http_response_code($status); header('Content-Type: application/json; charset=utf-8'); header('Cache-Control: no-store');
    echo json_encode(['error' => $message], JSON_UNESCAPED_UNICODE); exit;
}
function proxy_api(string $uri): never {
    $method = $_SERVER['REQUEST_METHOD'];
    if (!in_array($method, ['GET', 'POST'], true)) json_error('不支援此操作', 405);
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > MAX_UPLOAD_BYTES) json_error('上傳總量不可超過 32 MB', 413);
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    $scheme = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https' : 'http';
    if ($origin && $origin !== $scheme . '://' . $_SERVER['HTTP_HOST']) json_error('不接受跨網站操作', 403);
    if ($method === 'POST' && !str_starts_with($_SERVER['HTTP_AUTHORIZATION'] ?? '', 'Bearer ')) {
        web_session();
        if (!hash_equals($_SESSION['csrf'], $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '')) json_error('頁面已過期，請重新整理後再試', 403);
        session_write_close();
    }
    $type = $_SERVER['CONTENT_TYPE'] ?? 'application/json'; $body = '';
    if (str_starts_with($type, 'multipart/form-data')) {
        $boundary = 'photo_' . bin2hex(random_bytes(18));
        foreach ($_POST as $name => $value) {
            if (!is_scalar($value)) continue;
            $body .= '--' . $boundary . "\r\nContent-Disposition: form-data; name=\"" . preg_replace('/[^a-zA-Z0-9_]/', '', $name) . "\"\r\n\r\n" . $value . "\r\n";
        }
        foreach ($_FILES as $field => $info) {
            $names = is_array($info['name']) ? $info['name'] : [$info['name']];
            foreach ($names as $i => $original) {
                $error = is_array($info['error']) ? $info['error'][$i] : $info['error'];
                if ($error !== UPLOAD_ERR_OK) json_error('照片上傳失敗，請確認每張不超過 8 MB', 400);
                $tmp = is_array($info['tmp_name']) ? $info['tmp_name'][$i] : $info['tmp_name'];
                if (!is_uploaded_file($tmp)) json_error('無效的上傳檔案', 400);
                $name = preg_replace('/[^a-zA-Z0-9_.-]/', '_', basename($original));
                $fieldName = preg_replace('/[^a-zA-Z0-9_]/', '', $field);
                $mime = (new finfo(FILEINFO_MIME_TYPE))->file($tmp);
                $body .= '--' . $boundary . "\r\nContent-Disposition: form-data; name=\"$fieldName\"; filename=\"$name\"\r\nContent-Type: $mime\r\n\r\n" . file_get_contents($tmp) . "\r\n";
            }
        }
        $body .= '--' . $boundary . "--\r\n"; $type = 'multipart/form-data; boundary=' . $boundary;
    } else { $body = file_get_contents('php://input'); }
    [$status, $headers, $data] = backend_request($uri, $method, $body, $type);
    http_response_code($status); forward_cookies($headers);
    header('Content-Type: ' . ($headers['content-type'][0] ?? 'application/json'));
    header('Cache-Control: no-store'); header('X-Content-Type-Options: nosniff'); header('X-Frame-Options: DENY');
    echo $data; exit;
}
