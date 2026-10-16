"""Limit failed device-code attempts per direct client IP (single-process server)."""
from collections import OrderedDict
from threading import Lock
from time import monotonic
from flask import request, jsonify
from app.controllers.device_controller import DeviceController


def install_device_guard(app):
    failures = OrderedDict()
    lock = Lock()

    @app.before_request
    def check_device_code():
        header = request.headers.get("Authorization", "")
        if not request.path.startswith("/api/") or not header.startswith("Bearer "):
            return
        address = request.remote_addr or "unknown"
        now = monotonic()
        with lock:
            attempts = [t for t in failures.get(address, []) if now - t < 60]
            if len(attempts) >= 10:
                response = jsonify(error="裝置碼錯誤次數過多，請 60 秒後再試")
                response.headers["Retry-After"] = "60"
                return response, 429
            if not DeviceController.verify_token(header[7:]):
                attempts.append(now)
                failures[address] = attempts
                failures.move_to_end(address)
                if len(failures) > 10000:
                    failures.popitem(last=False)
                return jsonify(error="裝置碼無效"), 401
