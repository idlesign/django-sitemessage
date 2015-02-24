from django.conf import settings


# Module name to search sitemessage preferences in.
APP_MODULE_NAME = getattr(settings, 'SITEMESSAGE_APP_MODULE_NAME', 'sitemessages')

# Whether to register builtin message types.
INIT_BUILTIN_MESSAGE_TYPES = getattr(settings, 'SITEMESSAGE_INIT_BUILTIN_MESSAGE_TYPES', True)

# Priority for messages sent by Django Email backend (sitemessage.backends.EmailBackend).
EMAIL_BACKEND_MESSAGES_PRIORITY = getattr(settings, 'SITEMESSAGE_EMAIL_BACKEND_MESSAGES_PRIORITY', None)

# Message type alias for messages sent `schedule_email` shortcut.
DEFAULT_SHORTCUT_EMAIL_MESSAGES_TYPE = getattr(settings, 'SITEMESSAGE_DEFAULT_SHORTCUT_EMAIL_MESSAGES_TYPE', 'smtp')

# Site URL to use in messages.
SITE_URL = getattr(settings, 'SITEMESSAGE_SITE_URL', None)
