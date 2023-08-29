import os
import logging.config

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
from django.urls import reverse_lazy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',

    'fl_meters',
    'fl_dashboard',
    'django_google_maps',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'flowless_dashboard.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'flowless_dashboard.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/
STATIC_URL = '/static/'

REST_FRAMEWORK = {
    # Classes may be overridden on a per-view basis inside each ViewSet class

    # Request is allowed if ALL Permission Classes successfully permit request.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAdminUser',
    ),
    # Request is allowed if ANY Authentication Class successfully authenticates request.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'fl_meters.authentication.MeterTokenAuthentication',
    )
}

GOOGLE_MAPS_API_KEY = 'apiKey'

LOGIN_URL = reverse_lazy('login')
LOGIN_REDIRECT_URL = reverse_lazy('dashboard:home')
LOGOUT_REDIRECT_URL = 'http://www.flowless.co'

DATE_FORMAT = "%d/%m/%Y"
if os.name == 'nt':  # Windows
    TIME_FORMAT = "%#I:%M %p"
    HOURS_FORMAT = "%#I %p"
else:
    TIME_FORMAT = "%-I:%M %p"
    HOURS_FORMAT = "%-I %p"
DATETIME_FORMAT = DATE_FORMAT + ", " + TIME_FORMAT

PRECISE_TIME_FORMAT = "%H:%M:%S"
PRECISE_DATETIME_FORMAT = DATE_FORMAT + ", " + PRECISE_TIME_FORMAT

VERBOSE_TIME_FORMAT = "%H:%M:%S+%z(%Z)"
VERBOSE_DATE_FORMAT = "%d/%m/%Y"
VERBOSE_DATETIME_FORMAT = VERBOSE_DATE_FORMAT + ", " + VERBOSE_TIME_FORMAT

# == Machine-specific Settings ==
try:
    from .local_settings import *
except ImportError:
    raise Exception("A local_settings.py file is required to run this project")
