import os
from pathlib import Path
import dj_database_url
import environ



# BASE_DIR: project root (where manage.py lives)
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialise environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY
#ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])


# Paystack settings
PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = env('PAYSTACK_PUBLIC_KEY')
PAYSTACK_VERIFY_URL = env('PAYSTACK_VERIFY_URL')

# Email Configuration (use env consistently)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER
EMAIL_TIMEOUT = 15

# Contact notification email
CONTACT_NOTIFICATION_EMAIL = EMAIL_HOST_USER

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',

    'main',  # your app
    'signal',
    'channels',
    "chat",
    
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
        
    'main.middleware.ForcePasswordChangeMiddleware',
  # ✅ Keep only this
]


ROOT_URLCONF = 'stemsite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Adjust template dirs as needed; this points to <BASE_DIR>/main/templates
        'DIRS': [
            BASE_DIR / 'main' / 'templates',
            BASE_DIR / 'chat' / 'templates',
        ],
        
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'main.context_processors.guest_chat_id',
            ],
        },
    },
]

WSGI_APPLICATION = 'stemsite.wsgi.application'


ASGI_APPLICATION = 'stemsite.asgi.application' 



# =========================
# REDIS CONFIG (LOCAL + RENDER) CHANNELE_LAYERS
# =========================
# ---------- Redis URL ----------
if os.environ.get("REDIS_HOST") and os.environ.get("REDIS_PORT"):
    # Render Key-Value Redis
    REDIS_HOST = os.environ.get("REDIS_HOST")
    REDIS_PORT = os.environ.get("REDIS_PORT")
    REDIS_USERNAME = os.environ.get("REDIS_USERNAME", "")
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
    REDIS_SSL = os.environ.get("REDIS_SSL", "False") == "True"

    if REDIS_USERNAME:
        REDIS_URL = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    elif REDIS_PASSWORD:
        REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    else:
        REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"

    # Only replace scheme with rediss:// if SSL is True
    if REDIS_SSL:
        REDIS_URL = REDIS_URL.replace("redis://", "rediss://")
else:
    # Local Redis fallback
    REDIS_URL = "redis://127.0.0.1:6379"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}



# Check if Render Redis variables exist, otherwise fallback to local
if os.environ.get("REDIS_HOST") and os.environ.get("REDIS_PORT"):
    # Render Key-Value (or any external Redis)
    REDIS_HOST = os.environ.get("REDIS_HOST")
    REDIS_PORT = os.environ.get("REDIS_PORT")
    REDIS_USERNAME = os.environ.get("REDIS_USERNAME", None)
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
    REDIS_SSL = os.environ.get("REDIS_SSL", "False") == "True"

    REDIS_URL = f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}" if REDIS_USERNAME else f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    if REDIS_SSL:
        REDIS_URL = REDIS_URL.replace("redis://", "rediss://")
else:
    # Local Redis fallback
    REDIS_URL = "redis://127.0.0.1:6379"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}




# -----------------------------
# Database - PostgreSQL only
# -----------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=not DEBUG  # SSL in production
    )
}


# Authentication
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'portal'
LOGOUT_REDIRECT_URL = '/'

# Custom error handler
HANDLER403 = 'main.views.custom_403_view'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
      {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'main' / 'static']  # development static files

STATIC_ROOT = BASE_DIR / 'staticfiles'  # where collectstatic gathers static files

# WhiteNoise static files storage
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Admins who will receive system notifications
ADMINS = [
    ("Admin", EMAIL_HOST_USER),  # You can add more tuples: ("Name", "email")
]

# Domain handling
if DEBUG:  # Development
    SITE_DOMAIN = "http://127.0.0.1:8000"
else:      # Production
    SITE_DOMAIN = "https://stemcodemaster.com"
    

#----------Change to your real URL in Production ------------
SITE_URL = "http://127.0.0.1:8000"