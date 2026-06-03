#!/bin/sh
# Render injects $PORT automatically; fall back to 10000 for local Docker runs
export PORT=${PORT:-10000}
exec supervisord -n -c /etc/supervisor/supervisord.conf
