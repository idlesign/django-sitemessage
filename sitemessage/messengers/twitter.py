from django.utils.translation import ugettext as _

from .base import MessengerBase
from ..exceptions import MessengerWarmupException


class TwitterMessenger(MessengerBase):
    """Implements to Twitter message delivery using `twitter` module.

    https://github.com/sixohsix/twitter

    """

    alias = 'twitter'
    title = _('Tweet')
    _session_started = False

    def __init__(self, api_key, api_secret, access_token, access_token_secret):
        """Configures messenger.

        Register Twitter application here - https://apps.twitter.com/

        :param api_key: API key for Twitter client
        :param api_secret: API secret for Twitter client
        :param access_token: Access token for an account to tweet from
        :param access_token_secret: Access token secret for an account to tweet from
        """
        import twitter

        self.lib = twitter
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret

    @classmethod
    def get_address(cls, recipient):
        return getattr(recipient, 'twitter', None) or recipient

    def _test_message(self, to, text):
        return self._send_message(self._build_message(to, text))

    def before_send(self):
        try:
            self.api = self.lib.Twitter(auth=self.lib.OAuth(self.access_token, self.access_token_secret, self.api_key, self.api_secret))
            self._session_started = True
        except self.lib.api.TwitterError as e:
            raise MessengerWarmupException('Twitter Error: %s' % e)
    
    @classmethod
    def _build_message(cls, to, text):
        if to:
            if not to.startswith('@'):
                to = '@%s' % to
            to = '%s ' % to
        else:
            to = ''
        msg = '%s%s' % (to, text)
        return msg

    def _send_message(self, msg):
        return self.api.statuses.update(status=msg)

    def send(self, message_cls, message_model, dispatch_models):
        if self._session_started:
            for dispatch_model in dispatch_models:
                msg = self._build_message(dispatch_model.address, dispatch_model.message_cache)
                try:
                    self._send_message(msg)
                    self.mark_sent(dispatch_model)
                except Exception as e:
                    self.mark_error(dispatch_model, e, message_cls)
