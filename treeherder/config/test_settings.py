from treeherder.config.settings import *

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "db_cache": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}
