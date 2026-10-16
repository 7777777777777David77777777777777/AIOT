<?php
declare(strict_types=1);
require_once __DIR__ . '/bootstrap.php';
[$status] = backend_request('/api/health');
http_response_code($status === 200 ? 200 : 503);
header('Content-Type: application/json');
echo json_encode(['ok' => $status === 200]);
