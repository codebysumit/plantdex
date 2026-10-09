"""
Gunicorn Production Server Configuration for PlantDex
Tuned for Render CPU-only instances with 512 MB RAM constraint.
"""
import os
import multiprocessing

# Bind to Render's dynamic PORT
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Concurrency rule: 1 worker and 4 threads to keep RAM below 200 MB
# Multiple workers would duplicate the TFLite model and exhaust 512 MB RAM.
workers = 1
threads = 4
worker_class = "gthread"

# Timeouts
timeout = 60
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Memory protection
max_requests = 1000
max_requests_jitter = 50

# Preload app to initialize TFLite model and SQLite seed once before threading
preload_app = True


def on_starting(server):
    print("PlantDex server booting up on Render...")
