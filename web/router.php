<?php
// Local development router. Deploy web/ as the document root in production.
declare(strict_types=1);
require __DIR__ . '/bootstrap.php';
$uri = $_SERVER['REQUEST_URI']; $path = rawurldecode(parse_url($uri, PHP_URL_PATH) ?: '/');
if (str_starts_with($path, '/api/')) proxy_api($uri);
if (str_starts_with($path, '/static/')) {
    $root = realpath(__DIR__ . '/../app/static');
    $file = realpath($root . substr($path, 7));
    if ($file && str_starts_with($file, $root . DIRECTORY_SEPARATOR) && is_file($file)) {
        $types = ['css'=>'text/css', 'js'=>'text/javascript', 'woff'=>'font/woff', 'woff2'=>'font/woff2', 'ttf'=>'font/ttf', 'png'=>'image/png', 'svg'=>'image/svg+xml'];
        header('Content-Type: ' . ($types[pathinfo($file, PATHINFO_EXTENSION)] ?? 'application/octet-stream'));
        header('X-Content-Type-Options: nosniff'); readfile($file); exit;
    }
}
if ($path === '/' || $path === '/index.php') { require __DIR__ . '/index.php'; exit; }
if ($path === '/login.php') { require __DIR__ . '/login.php'; exit; }
if ($path === '/health.php') { require __DIR__ . '/health.php'; exit; }
http_response_code(404); echo '找不到此頁面';
