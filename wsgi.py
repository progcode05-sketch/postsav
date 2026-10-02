"""Production WSGI entry point used by Gunicorn."""
from app import app

application = app
