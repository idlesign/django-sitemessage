from .base import MessageBase

from django.utils.translation import ugettext as _


class PlainTextMessage(MessageBase):
    """Simple plain text message class to allow schedule_messages()
    to accept message as a simple string instead of a message object.

    """

    alias = 'plain'
    title = _('Text notification')

    def __init__(self, text):
        super(PlainTextMessage, self).__init__({self.SIMPLE_TEXT_ID: text})
