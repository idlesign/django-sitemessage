from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SitemessageConfig(AppConfig):
    """Sitemessage configuration."""

    name = 'sitemessage'
    verbose_name = _('Messaging')
