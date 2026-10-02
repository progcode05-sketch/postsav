"""Gunicorn settings sized for a 512 MB single-instance beta deployment."""
import os


bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# One process keeps the application comfortably inside 512 MB. Threads share
# code and clients; the app caps simultaneous download jobs itself (limits.py).
workers = 1
worker_class = 'gthread'
threads = int(os.environ.get('WEB_THREADS', '4'))

# Media extraction can take longer than an ordinary web request.
timeout = int(os.environ.get('REQUEST_TIMEOUT', '300'))
graceful_timeout = 30
keepalive = 5

# Periodic recycling limits damage from slow native/library memory growth.
max_requests = int(os.environ.get('MAX_REQUESTS_PER_WORKER', '250'))
max_requests_jitter = 25

accesslog = '-'
# %(U)s is the path without its query string, so download session tokens and
# post links are never written to the access log.
access_log_format = '%(h)s fwd=%({x-forwarded-for}i)s cf=%({cf-connecting-ip}i)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
capture_output = True

# Trust forwarded headers only from the hosting platform's proxy path. Render
# overwrites forwarding headers before proxying requests to the service.
forwarded_allow_ips = os.environ.get('FORWARDED_ALLOW_IPS', '*')

# Do not preload: the cleanup thread and Redis client start per worker. Without
# REDIS_URL sessions are process-local, so keep a single worker.
preload_app = False
