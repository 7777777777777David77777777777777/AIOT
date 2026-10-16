"""Persistent task worker. Safe to restart; unfinished leases are reclaimed."""
import os
import signal
import threading
from app import create_app
from app.task_service import run_one


def main():
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    app = create_app()
    print('Task worker ready', flush=True)
    while not stop.is_set():
        try:
            with app.app_context():
                active = run_one()
        except Exception:
            active = False
            print('Task worker database unavailable; retrying', flush=True)
        if not active:
            stop.wait(1)


if __name__ == '__main__':
    main()
