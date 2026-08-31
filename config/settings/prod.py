from .base import *

# Debug settings
DEBUG = False

# Allowed hosts
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
