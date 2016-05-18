from django.utils.translation import ugettext as _

from .base import MessengerBase
from ..exceptions import MessengerException


class FacebookMessengerException(MessengerException):
    """Exceptions raised by Facebook messenger."""


class FacebookMessenger(MessengerBase):
    """Implements Facebook page wall message publishing.

    Uses `requests` module: https://pypi.python.org/pypi/requests

    Steps to be done:

    1. Create FB application for your website at https://developers.facebook.com/apps/

    2. Create a page
       (possibly at https://developers.facebook.com/apps/{app_id}/settings/advanced/ under `App Page`
       - replace {app_id} with your application ID).

    3. Go to Graph API Explorer - https://developers.facebook.com/tools/explorer/
       3.1. Pick your application from top right dropdown.
       3.2. `Get User Token` using dropdown near Access Token field. Check `manage_pages` permission.

    """

    alias = 'fb'
    title = _('Facebook')

    _graph_version = '2.6'

    _url_base = 'https://graph.facebook.com'
    _url_versioned = _url_base + '/v' + _graph_version
    _tpl_url_feed = _url_versioned + '/%(page_id)s/feed'

    def __init__(self, page_access_token):
        """Configures messenger.

        :param str page_access_token: Unique authentication token of your FB page.
            One could be generated from User token using .get_page_access_token().

        """
        import requests

        self.lib = requests
        self.access_token = page_access_token

    def get_page_access_token(self, app_id, app_secret, user_token):
        """Returns a dictionary of never expired page token indexed by page names.

        :param str app_id: Application ID
        :param str app_secret: Application secret
        :param str user_token: User short-lived token
        :rtype: dict

        """
        url_extend = (
            self._url_base + '/oauth/access_token?grant_type=fb_exchange_token&'
                             'client_id=%(app_id)s&client_secret=%(app_secret)s&fb_exchange_token=%(user_token)s')

        response = self.lib.get(url_extend % {'app_id': app_id, 'app_secret': app_secret, 'user_token': user_token})

        user_token_long_lived = response.text.split('=')[-1]

        response = self.lib.get(self._url_versioned + '/me/accounts?access_token=%s' % user_token_long_lived)
        json = response.json()

        tokens = {item['name']: item['access_token'] for item in json['data'] if item.get('access_token')}

        return tokens

    def _test_message(self, to, text):
        return self._send_message(text)

    def _send_message(self, text):

        try:
            # Automatically deduce message type.
            message_type = 'link' if text.startswith('http') else 'message'

            response = self.lib.post(
                self._tpl_url_feed % {'page_id': 'me'},
                data={'access_token': self.access_token, message_type: text})

            json = response.json()

            if 'error' in json:
                error = json['error']
                raise FacebookMessengerException('%s: %s' % (error['code'], error['message']))

            return json['id']  # Returns post ID.

        except self.lib.exceptions.RequestException as e:
            raise FacebookMessengerException(e)

    def send(self, message_cls, message_model, dispatch_models):
        for dispatch_model in dispatch_models:
            try:
                self._send_message(dispatch_model.message_cache)
                self.mark_sent(dispatch_model)

            except Exception as e:
                self.mark_error(dispatch_model, e, message_cls)
