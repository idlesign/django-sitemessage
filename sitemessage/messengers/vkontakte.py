from django.utils.translation import gettext as _

from .base import RequestsMessengerBase
from ..exceptions import MessengerException


class VKontakteMessengerException(MessengerException):
    """Exceptions raised by VKontakte messenger."""


class VKontakteMessenger(RequestsMessengerBase):
    """Implements VKontakte page wall message publishing.

    Steps to be done:

    1. Create a user/community page.
    2. Create `Standalone` application at http://vk.com/apps?act=manage
    3. Get your Application ID (under Settings menu item in left menu)
    4. To generate an access token go to using your browser:

        https://oauth.vk.com/authorize?client_id={app_id}&scope=wall,offline&display=page&response_type=token
        &v=5.52&redirect_uri=https://oauth.vk.com/blank.html
        
        * Replace {app_id} with actual application ID.

    5. Copy token from URL in browser (symbols after `access_token=` but before &)
    6. Use this token.

    """
    alias = 'vk'
    title = _('VKontakte')

    address_attr = 'vkontakte'

    _url_wall = 'https://api.vk.com/method/wall.post'

    def __init__(self, access_token, proxy=None):
        """Configures messenger.

        :param str access_token: Unique authentication token to access your VK user/community page.
        :param dict|Callable: Dictionary of proxy settings,
            or a callable returning such a dictionary.

        """
        super().__init__(proxy=proxy)
        self.access_token = access_token

    def _send_message(self, msg, to=None):

        # Automatically deduce message type.
        message_type = 'attachments' if msg.startswith('http') else 'message'

        json = self.post(
            url=self._url_wall,
            data={
                message_type: msg,
                'owner_id': to,
                'from_group': 1,
                'access_token': self.access_token,
                'v': '5.73',
            })

        if 'error' in json:
            error = json['error']
            raise VKontakteMessengerException('%s: %s' % (error['error_code'], error['error_msg']))

        return json['response']['post_id']  # Returns post ID.
