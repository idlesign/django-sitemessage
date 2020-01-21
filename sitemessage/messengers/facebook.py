from django.utils.translation import gettext as _

from .base import RequestsMessengerBase
from ..exceptions import MessengerException


class FacebookMessengerException(MessengerException):
    """Exceptions raised by Facebook messenger."""


class FacebookMessenger(RequestsMessengerBase):
    """Implements Facebook page wall message publishing.

    Steps to be done:

    1. Create FB application for your website at https://developers.facebook.com/apps/

    2. Create a page
       (possibly at https://developers.facebook.com/apps/{app_id}/settings/advanced/ under `App Page`
       - replace {app_id} with your application ID).

    3. Go to Graph API Explorer - https://developers.facebook.com/tools/explorer/
       3.1. Pick your application from top right dropdown.
       3.2. `Get User Token` using dropdown near Access Token field. Check `manage_pages` permission.
       
    4. Get page access token from your user token and application credentials using .get_page_access_token().

    """

    alias = 'fb'
    title = _('Facebook')

    _graph_version = '2.6'

    _url_base = 'https://graph.facebook.com'
    _url_versioned = _url_base + '/v' + _graph_version
    _tpl_url_feed = _url_versioned + '/%(page_id)s/feed'

    def __init__(self, page_access_token, proxy=None):
        """Configures messenger.

        :param str page_access_token: Unique authentication token of your FB page.
            One could be generated from User token using .get_page_access_token().

        """
        super().__init__(proxy=proxy)
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

        response = self.get(url_extend % {'app_id': app_id, 'app_secret': app_secret, 'user_token': user_token})
        user_token_long_lived = response.split('=')[-1]

        json = self.get(self._url_versioned + '/me/accounts?access_token=%s' % user_token_long_lived, json=True)

        tokens = {item['name']: item['access_token'] for item in json['data'] if item.get('access_token')}

        return tokens

    def _send_message(self, msg, to=None):

        # Automatically deduce message type.
        message_type = 'link' if msg.startswith('http') else 'message'

        json = self.post(
            url=self._tpl_url_feed % {'page_id': 'me'},
            data={'access_token': self.access_token, message_type: msg})

        if 'error' in json:
            error = json['error']
            raise FacebookMessengerException('%s: %s' % (error['code'], error['message']))

        return json['id']  # Returns post ID.
