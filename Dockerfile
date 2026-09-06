FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[google-calendar,google-gmail]"

RUN useradd --create-home --uid 10001 lifeos
RUN mkdir -p /data/private && chown -R lifeos:lifeos /data
USER lifeos

EXPOSE 8000

CMD ["sh", "-c", "life-os serve --host 0.0.0.0 --port ${PORT:-8000}"]
