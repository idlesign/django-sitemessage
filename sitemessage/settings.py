from django.conf import settings

# Module name to search sitemessage preferences in.
APP_MODULE_NAME = getattr(settings, 'SITEMESSAGE_APP_MODULE_NAME', 'sitemessages')

# Whether to register builtin message types.
BOOTSTRAP_BUILTIN_MESSAGE_TYPES = getattr(settings, 'SITEMESSAGE_BOOTSTRAP_BUILTIN_MESSAGE_TYPES', True)
