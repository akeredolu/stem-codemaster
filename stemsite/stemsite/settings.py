import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from pathlib import Path
import dj_database_url
import environ


# BASE_DIR: project root (where manage.py lives)
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialise environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


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
    "cloudinary",
    "cloudinary_storage",

    'main',  
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
# CLOUDINARY MEDIA STORAGE
# =========================

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": env("CLOUDINARY_API_KEY"),
    "API_SECRET": env("CLOUDINARY_API_SECRET"),
}

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

MEDIA_URL = "/media/"  


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