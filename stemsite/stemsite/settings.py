import environ
import os
from pathlib import Path
import dj_database_url

import cloudinary
import cloudinary.uploader
import cloudinary.api

BASE_DIR = Path(__file__).resolve().parent.parent  # stemsite/stemsite -> stemsite

# Initialise environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    env.read_env(ENV_FILE)
else:
    print("⚠️ .env file not found, relying on system env vars")


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# SECURITY
SECRET_KEY = env('DJANGO_SECRET_KEY')

DEBUG = env.bool('DJANGO_DEBUG', default=False)

ALLOWED_HOSTS = env.list(
    'DJANGO_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '.onrender.com']
)

CSRF_TRUSTED_ORIGINS = env.list(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    default=['https://stem-codemaster.onrender.com']
)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True


# Paystack settings
PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = env('PAYSTACK_PUBLIC_KEY')
PAYSTACK_VERIFY_URL = env('PAYSTACK_VERIFY_URL')


# =========================
# EMAIL CONFIGURATION (Brevo SMTP + Verified Gmail sender)
# =========================

# Use env vars for all sensitive info
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp-relay.brevo.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)

# Brevo SMTP credentials (must always be Brevo login)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='9e5404001@smtp-brevo.com')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='441cae9f7db479307d9459745fc5d72bdf50de58db927cfd4a90074dceece5ff-cG1cLMEwzCzX7V3r')

# Verified sender email (can be Gmail for now)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='STEM CodeMaster <code247.me@gmail.com>')
SERVER_EMAIL = env('SERVER_EMAIL', default='STEM CodeMaster <code247.me@gmail.com>')

# Optional: email for contact form notifications
CONTACT_NOTIFICATION_EMAIL = env('CONTACT_NOTIFICATION_EMAIL', default=EMAIL_HOST_USER)

ADMIN_EMAIL = env('CONTACT_NOTIFICATION_EMAIL', default=EMAIL_HOST_USER)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    "cloudinary",
    "cloudinary_storage",
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',

    'main',  
    'signal',
    'channels',
    "chat",   
    'services',
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

]


ROOT_URLCONF = 'stemsite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        
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
# REDIS / CHANNELS (LOCAL + RENDER)
# =========================

REDIS_URL = env(
    "REDIS_URL",
    default="redis://127.0.0.1:6379"
)

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
# =========================
# CLOUDINARY CONFIG
# =========================

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": env("CLOUDINARY_API_KEY"),
    "API_SECRET": env("CLOUDINARY_API_SECRET"),
    "RESOURCE_TYPE": "raw",
}

# =========================
# STORAGE CONFIG (DJANGO 5+)
# =========================

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/"


# Domain handling
if DEBUG:  # Development
    SITE_DOMAIN = "http://127.0.0.1:8000"
else:      # Production
    SITE_DOMAIN = "https://stemcodemaster.com"
    

#----------Change to your real URL in Production ------------
SITE_URL = "http://127.0.0.1:8000"

# Admins who will receive system notifications
ADMINS = [
    ("Admin", EMAIL_HOST_USER),  # You can add more tuples: ("Name", "email")
]