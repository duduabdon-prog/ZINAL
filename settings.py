import os
from decouple import config
import dj_database_url

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Usar banco do Render se existir
DATABASES = {
    'default': dj_database_url.config(default=config('DATABASE_URL', default='sqlite:///db.sqlite3'))
}

# Arquivos estáticos
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Whitenoise para servir arquivos estáticos
MIDDLEWARE = [
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE,
]
