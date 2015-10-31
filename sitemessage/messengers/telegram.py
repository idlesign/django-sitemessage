from django.utils.translation import ugettext as _

from .base import MessengerBase
from ..exceptions import MessengerWarmupException, MessengerException


class TelegramMessengerException(MessengerException):
    """Exceptions raised by Telegram messenger."""


class TelegramMessenger(MessengerBase):
    """Implements Telegram message delivery vie Telegram Bot API.

    Uses `requests` module: https://pypi.python.org/pypi/requests

    """

    alias = 'telegram'
    title = _('Telegram')

    _session_started = False
    _tpl_url = 'https://api.telegram.org/bot%(token)s/%(method)s'

    def __init__(self, auth_token):
        """Configures messenger.

        Register a Telegram Bot using instructions from https://core.telegram.org/bots/api

        :param auth_token: Bot unique authentication token
        """
        import requests

        self.lib = requests
        self.auth_token = auth_token

    @classmethod
    def get_address(cls, recipient):
        return getattr(recipient, 'telegram', None) or recipient

    def _test_message(self, to, text):
        return self._send_message(self._build_message(to, text))

    def _verify_bot(self):
        """Sends an API command to test whether bot is authorized."""
        self._send_command('getMe')

    def before_send(self):
        try:
            self._verify_bot()
            self._session_started = True
        except TelegramMessengerException as e:
            raise MessengerWarmupException('Telegram Error: %s' % e)

    @classmethod
    def _build_message(cls, to, text):
        return {'chat_id': to, 'text': text}

    def _send_command(self, method_name, data=None):
        """Sends a command to API.

        :param str method_name:
        :param dict data:
        :return:
        """
        try:
            response = self.lib.post(self._tpl_url % {'token': self.auth_token, 'method': method_name}, data=data)
            json = response.json()

            if not json['ok']:
                raise TelegramMessengerException(json['description'])

        except self.lib.exceptions.RequestException as e:
            raise TelegramMessengerException(e)

    def _send_message(self, msg):
        return self._send_command('sendMessage', msg)

    def send(self, message_cls, message_model, dispatch_models):
        if self._session_started:
            for dispatch_model in dispatch_models:
                msg = self._build_message(dispatch_model.address, dispatch_model.message_cache)
                try:
                    self._send_message(msg)
                    self.mark_sent(dispatch_model)
                except Exception as e:
                    self.mark_error(dispatch_model, e, message_cls)
