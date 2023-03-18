from unittest.mock import MagicMock, patch

from sitemessage.messages.base import MessageBase
from sitemessage.messages.plain import PlainTextMessage
from sitemessage.messengers.base import MessengerBase
from sitemessage.messengers.facebook import FacebookMessenger
from sitemessage.messengers.smtp import SMTPMessenger
from sitemessage.messengers.telegram import TelegramMessenger
from sitemessage.messengers.twitter import TwitterMessenger
from sitemessage.messengers.vkontakte import VKontakteMessenger
from sitemessage.messengers.xmpp import XMPPSleekMessenger
from sitemessage.toolbox import register_builtin_message_types
from sitemessage.utils import register_message_types
from sitemessage.utils import register_messenger_objects


class MockException(Exception):
    """This will prevent `catching classes that do not inherit from BaseException is not allowed` errors
    when `mock_thirdparty` is used.

    """


def mock_thirdparty(name, func, mock=None):
    if mock is None:
        mock = MagicMock()

    with patch.dict('sys.modules', {name: mock}):
        result = func()

    return result


messenger_smtp = mock_thirdparty('smtplib', lambda: SMTPMessenger(login='someone', use_tls=True))

messenger_xmpp = mock_thirdparty('sleekxmpp', lambda: XMPPSleekMessenger('somjid', 'somepasswd'))
messenger_xmpp._session_started = True

messenger_twitter = mock_thirdparty('twitter', lambda: TwitterMessenger('key', 'secret', 'token', 'token_secret'))
messenger_twitter.lib = MagicMock()

messenger_telegram = mock_thirdparty('requests', lambda: TelegramMessenger(
    'bottoken', proxy={'https': 'socks5://user:pass@host:port'}))
messenger_telegram.lib = MagicMock()
messenger_telegram.lib.exceptions.RequestException = MockException

messenger_fb = mock_thirdparty('requests', lambda: FacebookMessenger('pagetoken', proxy=lambda: {'https': '0.0.0.0'}))
messenger_fb.lib = MagicMock()
messenger_fb.lib.exceptions.RequestException = MockException

messenger_vk = mock_thirdparty('requests', lambda: VKontakteMessenger('apptoken'))
messenger_vk.lib = MagicMock()
messenger_vk.lib.exceptions.RequestException = MockException

register_messenger_objects(
    messenger_smtp,
    messenger_xmpp,
    messenger_twitter,
    messenger_telegram,
    messenger_fb,
    messenger_vk,
)

register_builtin_message_types()


WONDERLAND_DOMAIN = '@wonderland'


class MessengerForTest(MessengerBase):

    title = 'Test messenger'
    alias = 'test_messenger'
    last_send = None

    def __init__(self, login, password):
        self.login = login
        self.password = password

    def _test_message(self, to, text):
        return f'triggered send to `{to}`'

    @classmethod
    def get_address(cls, recipient):
        from django.contrib.auth.models import User

        if isinstance(recipient, User):
            recipient = f'user_{recipient.username}'

        return f'{recipient}{WONDERLAND_DOMAIN}'

    def send(self, message_cls, message_model, dispatch_models):
        self.last_send = {
            'message_cls': message_cls,
            'dispatch_models': dispatch_models,
            'message_model': message_model,
        }


class BuggyMessenger(MessengerBase):

    title = 'Buggy messenger'
    alias = 'buggy'

    def send(self, message_cls, message_model, dispatch_models):
        raise Exception('Damn it.')


class MessageForTest(MessageBase):

    alias = 'test_message'
    template_ext = 'html'
    title = 'Test message type'
    supported_messengers = ['smtp', 'test_messenger']


class MessagePlainForTest(PlainTextMessage):

    alias = 'testplain'
    priority = 10


class MessageGroupedForTest(PlainTextMessage):

    alias = 'testgroupped'
    group_mark = 'groupme'


class MessagePlainDynamicForTest(PlainTextMessage):

    alias = 'testplain_dyn'
    has_dynamic_context = True

    @classmethod
    def compile(cls, message, messenger, dispatch=None):
        return f'{message.context[MessageBase.SIMPLE_TEXT_ID]} -- {dispatch.address}'


register_messenger_objects(
    MessengerForTest('mylogin', 'mypassword'),
    BuggyMessenger(),
)

register_message_types(
    PlainTextMessage,
    MessageForTest,
    MessageGroupedForTest,
    MessagePlainForTest,
    MessagePlainDynamicForTest,
)
