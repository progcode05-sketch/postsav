FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    PUBLIC_MODE=1 \
    HOME=/tmp/app-home

WORKDIR /app

# ffmpeg merges separate video/audio streams. ca-certificates is explicit so
# platform HTTPS downloads continue to work if the base image changes.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py limits.py media_sources.py seo.py site_content.py wsgi.py gunicorn.conf.py ./
COPY templates ./templates
COPY static ./static

# The application writes only short-lived jobs under the system temp folder.
# Running as an unprivileged user limits the impact of an application bug.
RUN groupadd --system downloader \
    && useradd --system --gid downloader --home-dir /nonexistent --shell /usr/sbin/nologin downloader \
    && mkdir -p /tmp/app-home /tmp/social_downloader \
    && chown -R downloader:downloader /tmp/app-home /tmp/social_downloader

USER downloader

EXPOSE 10000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:application"]
