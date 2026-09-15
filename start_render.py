import os
import subprocess
import sys
import time

PORT = os.getenv("PORT", "8000")

worker = subprocess.Popen(
    [sys.executable, "-u", "-m", "backend.app.events.worker"],
    env=os.environ.copy(),
)

backend = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        PORT,
    ],
    env=os.environ.copy(),
)

try:
    while True:
        if worker.poll() is not None:
            print("[START] Worker stopped.")
            backend.terminate()
            sys.exit(1)

        if backend.poll() is not None:
            print("[START] Backend stopped.")
            worker.terminate()
            sys.exit(1)

        time.sleep(2)

except KeyboardInterrupt:
    print("[START] Shutting down...")
    worker.terminate()
    backend.terminate()