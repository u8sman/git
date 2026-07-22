import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", max(2, min(4, multiprocessing.cpu_count()))))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "90"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
worker_tmp_dir = "/dev/shm"
accesslog = "-"
errorlog = "-"
capture_output = True
loglevel = os.getenv("LOG_LEVEL", "info").lower()
forwarded_allow_ips = "*"
