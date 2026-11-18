FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KNOPS_HOME=/app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY samples ./samples

RUN useradd --create-home --uid 1001 knops \
    && mkdir -p /app/data /app/results \
    && chown -R knops:knops /app
USER knops

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/api/status', timeout=3)"

CMD ["sh", "-c", "python -m knowledge_ops ingest samples/docs && python -m knowledge_ops serve --host 0.0.0.0 --port 8020"]
