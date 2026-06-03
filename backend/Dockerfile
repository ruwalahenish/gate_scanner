FROM python:3.12-slim

WORKDIR /app

# supervisor (process manager) + curl (healthcheck) + gcc + libpq-dev (asyncpg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc libpq-dev supervisor curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY supervisord.conf /etc/supervisor/conf.d/gate.conf
COPY start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 10000

CMD ["./start.sh"]
