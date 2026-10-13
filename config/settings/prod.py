from .base import *

# Debug settings
DEBUG = False

# Allowed hosts
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Database: reuse connections instead of a new TLS handshake per request
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# HTTPS ends at Cloudflare; the tunnel forwards plain HTTP with this header.
# Trusting it is safe only while nothing but the tunnel can reach the app.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600

# Throttle counters, shared by the gunicorn workers; lost on restart, which is fine
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/tmp/racha-cache",
    }
}

# Without DEBUG, Django only mails errors to ADMINS; print them to the container log
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django": {"handlers": ["console"], "level": "ERROR"}},
}
