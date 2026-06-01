from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance — imported by main.py (to register on app.state)
# and by individual routers (to apply @limiter.limit decorators).
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
