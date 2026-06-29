FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests/fixtures ./tests/fixtures
COPY portfolio.entities.example.json xero.inbound.example.json xero.credentials.example.json ./

RUN pip install --no-cache-dir -e .

ENV XERO_MCP_CONFIG_DIR=/config
ENV PYTHONUNBUFFERED=1

EXPOSE 8766

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
