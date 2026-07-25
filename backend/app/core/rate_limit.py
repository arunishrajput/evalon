"""slowapi rate limiter, keyed by client IP. Applied to auth endpoints to slow
down credential-stuffing / registration-spam attempts."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
