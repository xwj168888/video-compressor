FROM python:3.12-slim

# Use Tsinghua apt mirror (for China)
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|http://deb.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Use PyPI mirror for China
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn gevent

COPY . .

ENV DATA_DIR=/data
ENV HOST=0.0.0.0
ENV PORT=5050

RUN mkdir -p /data/uploads /data/outputs /data/jobs

EXPOSE 5050

CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", \
     "--bind", "0.0.0.0:5050", "--timeout", "3600", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--log-level", "info", "web.app:app"]
