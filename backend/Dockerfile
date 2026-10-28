FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Some Python packages used by the embedding pipeline require libgomp at runtime.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 nexora \
    && useradd --uid 10001 --gid nexora --create-home --shell /usr/sbin/nologin nexora

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=nexora:nexora . ./
RUN mkdir -p /app/storage/documents /data/documents /home/nexora/.cache \
    && chown -R nexora:nexora /app/storage /data/documents /home/nexora/.cache

USER nexora

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
