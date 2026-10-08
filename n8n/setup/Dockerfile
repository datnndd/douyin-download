FROM n8nio/n8n:latest

USER root

RUN set -eux; \
    apk add --no-cache \
      ffmpeg \
      python3 \
      py3-pip \
      curl \
      yt-dlp \
    ; \
    mkdir -p /data/files; \
    chown -R node:node /data

USER node
