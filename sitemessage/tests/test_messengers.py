import pytest

from sitemessage.messengers.base import MessengerBase
from sitemessage.models import Subscription, DispatchError
from sitemessage.toolbox import recipients, schedule_messages, send_scheduled_messages
from sitemessage.utils import get_registered_messenger_objects
from .testapp.sitemessages import (
    WONDERLAND_DOMAIN, MessagePlainForTest, MessengerForTest, BuggyMessenger,
    messenger_fb,
    messenger_smtp,
    messenger_telegram,
    messenger_twitter,
    messenger_vk,
    messenger_xmpp,
)


def test_init_params():
    messengers = get_registered_messenger_objects()
    my = messengers['test_messenger']
    assert my.login == 'mylogin'
    assert my.password == 'mypassword'


def test_alias():
    messenger = type('MyMessenger', (MessengerBase,), {'alias': 'myalias'})
    assert messenger.get_alias() == 'myalias'

    messenger = type('MyMessenger', (MessengerBase,), {})
    assert messenger.get_alias() == 'MyMessenger'


def test_get_recipients_data(user_create):
    user = user_create(attributes=dict(username='myuser'))
    to = ['gogi', 'givi', user]

    r1 = MessengerForTest.structure_recipients_data(to)

    assert len(r1) == len(to)
    assert r1[0].address == 'gogi%s' % WONDERLAND_DOMAIN
    assert r1[0].messenger == 'test_messenger'
    assert r1[1].address == 'givi%s' % WONDERLAND_DOMAIN
    assert r1[1].messenger == 'test_messenger'
    assert r1[2].address == 'user_myuser%s' % WONDERLAND_DOMAIN
    assert r1[2].messenger == 'test_messenger'


def test_recipients():
    r = MessagePlainForTest.recipients('smtp', 'someone')
    assert len(r) == 1
    assert r[0].address == 'someone'


def test_send():
    m = MessengerForTest('l', 'p')
    m.send('message_cls', 'message_model', 'dispatch_models')

    assert m.last_send['message_cls'] == 'message_cls'
    assert m.last_send['message_model'] == 'message_model'
    assert m.last_send['dispatch_models'] == 'dispatch_models'

    m = BuggyMessenger()
    recipiets_ = recipients('test_messenger', ['a', 'b', 'c', 'd'])

    with pytest.raises(Exception):
        m.send('a buggy message', '', recipiets_)


def test_subscription(user_create):
    user1 = user_create(attributes=dict(username='first'))
    user2 = user_create(attributes=dict(username='second'))
    user2.is_active = False
    user2.save()

    Subscription.create(user1.id, MessagePlainForTest, MessengerForTest)
    Subscription.create(user2.id, MessagePlainForTest, MessengerForTest)
    assert len(MessagePlainForTest.get_subscribers(active_only=False)) == 2
    assert len(MessagePlainForTest.get_subscribers(active_only=True)) == 1


def assert_called_n(func, n=1):
    assert func.call_count == n
    func.call_count = 0


def test_exception_propagation(monkeypatch):
    schedule_messages('text', recipients('telegram', ''))
    schedule_messages('text', recipients('telegram', ''))

    def new_method(*args, **kwargs):
        raise Exception('telegram beforesend failed')

    monkeypatch.setattr(messenger_telegram, 'before_send', new_method)
    send_scheduled_messages()

    errors = list(DispatchError.objects.all())
    assert len(errors) == 2
    assert errors[0].error_log == 'telegram beforesend failed'
    assert errors[1].error_log == 'telegram beforesend failed'


class TestSMTPMessenger(object):

    def setup_method(self, method):
        messenger_smtp.smtp.sendmail.call_count = 0

    def test_get_address(self):
        r = object()
        assert messenger_smtp.get_address(r) == r

        r = type('r', (object,), dict(email='somewhere'))
        assert messenger_smtp.get_address(r) == 'somewhere'

    def test_send(self):
        schedule_messages('text', recipients('smtp', 'someone'))
        send_scheduled_messages()
        assert_called_n(messenger_smtp.smtp.sendmail)

    def test_send_fail(self):
        schedule_messages('text', recipients('smtp', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('smtp failed')

        old_method = messenger_smtp.smtp.sendmail
        messenger_smtp.smtp.sendmail = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'smtp failed'
            assert errors[0].dispatch.address == 'someone'
        finally:
            messenger_smtp.smtp.sendmail = old_method

    def test_send_test_message(self):
        messenger_smtp.send_test_message('someone', 'sometext')
        assert_called_n(messenger_smtp.smtp.sendmail)


class TestTwitterMessenger(object):

    def test_get_address(self):
        r = object()
        assert messenger_twitter.get_address(r) == r

        r = type('r', (object,), dict(twitter='somewhere'))
        assert messenger_twitter.get_address(r) == 'somewhere'

    def test_send(self):
        schedule_messages('text', recipients('twitter', 'someone'))
        send_scheduled_messages()
        messenger_twitter.api.statuses.update.assert_called_with(status='@someone text')

    def test_send_test_message(self):
        messenger_twitter.send_test_message('someone', 'sometext')
        messenger_twitter.api.statuses.update.assert_called_with(status='@someone sometext')

        messenger_twitter.send_test_message('', 'sometext')
        messenger_twitter.api.statuses.update.assert_called_with(status='sometext')

    def test_send_fail(self):
        schedule_messages('text', recipients('twitter', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('tweet failed')

        old_method = messenger_twitter.api.statuses.update
        messenger_twitter.api.statuses.update = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'tweet failed'
            assert errors[0].dispatch.address == 'someone'
        finally:
            messenger_twitter.api.statuses.update = old_method


class TestXMPPSleekMessenger(object):

    def test_get_address(self):
        r = object()
        assert messenger_xmpp.get_address(r) == r

        r = type('r', (object,), dict(jabber='somewhere'))
        assert messenger_xmpp.get_address(r) == 'somewhere'

    def test_send(self):
        schedule_messages('text', recipients('xmppsleek', 'someone'))
        send_scheduled_messages()
        messenger_xmpp.xmpp.send_message.assert_called_once_with(
            mtype='chat', mbody='text', mfrom='somjid', mto='someone'
        )

    def test_send_test_message(self):
        messenger_xmpp.send_test_message('someone', 'sometext')
        messenger_xmpp.xmpp.send_message.assert_called_with(
            mtype='chat', mbody='sometext', mfrom='somjid', mto='someone'
        )

    def test_send_fail(self):
        schedule_messages('text', recipients('xmppsleek', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('xmppsleek failed')

        old_method = messenger_xmpp.xmpp.send_message
        messenger_xmpp.xmpp.send_message = new_method
        messenger_xmpp._session_started = True
        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'xmppsleek failed'
            assert errors[0].dispatch.address == 'someone'
        finally:
            messenger_xmpp.xmpp.send_message = old_method


class TestTelegramMessenger(object):

    def setup_method(self, method):
        messenger_telegram._verify_bot()
        messenger_telegram.lib.post.call_count = 0

    def test_get_address(self):
        r = object()
        assert messenger_telegram.get_address(r) == r

        r = type('r', (object,), dict(telegram='chat_id'))
        assert messenger_telegram.get_address(r) == 'chat_id'

    def test_send(self):
        schedule_messages('text', recipients('telegram', '1234567'))
        send_scheduled_messages()
        assert_called_n(messenger_telegram.lib.post, 2)
        assert messenger_telegram.lib.post.call_args[1]['proxies'] == {'https': 'socks5://user:pass@host:port'}

    def test_send_test_message(self):
        messenger_telegram.send_test_message('someone', 'sometext')
        assert_called_n(messenger_telegram.lib.post)

        messenger_telegram.send_test_message('', 'sometext')
        assert_called_n(messenger_telegram.lib.post)

    def test_get_chat_ids(self):
        assert messenger_telegram.get_chat_ids() == []
        assert_called_n(messenger_telegram.lib.post)

    def test_send_fail(self):
        schedule_messages('text', recipients('telegram', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('telegram failed')

        old_method = messenger_telegram.lib.post
        messenger_telegram.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'telegram failed'
            assert errors[0].dispatch.address == 'someone'
        finally:
            messenger_telegram.lib.post = old_method


class TestFacebookMessenger(object):

    def setup_method(self, method):
        messenger_fb.lib.post.call_count = 0
        messenger_fb.lib.get.call_count = 0

    def test_send(self):
        schedule_messages('text', recipients('fb', ''))
        send_scheduled_messages()
        assert_called_n(messenger_fb.lib.post)
        assert messenger_fb.lib.post.call_args[1]['proxies'] == {'https': '0.0.0.0'}

    def test_send_test_message(self):
        messenger_fb.send_test_message('', 'sometext')
        assert_called_n(messenger_fb.lib.post)

        messenger_fb.send_test_message('', 'sometext')
        assert_called_n(messenger_fb.lib.post)

    def test_get_page_access_token(self):
        assert messenger_fb.get_page_access_token('app_id', 'app_secret', 'user_token') == {}
        assert_called_n(messenger_fb.lib.get, 2)

    def test_send_fail(self):
        schedule_messages('text', recipients('fb', ''))

        def new_method(*args, **kwargs):
            raise Exception('fb failed')

        old_method = messenger_fb.lib.post
        messenger_fb.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'fb failed'
            assert errors[0].dispatch.address == ''
        finally:
            messenger_fb.lib.post = old_method


class TestVKontakteMessenger(object):

    def setup_method(self, method):
        messenger_vk.lib.post.call_count = 0
        messenger_vk.lib.get.call_count = 0

    def test_send(self):
        schedule_messages('text', recipients('vk', '12345'))
        send_scheduled_messages()
        assert_called_n(messenger_vk.lib.post)

    def test_send_test_message(self):
        messenger_vk.send_test_message('12345', 'sometext')
        assert_called_n(messenger_vk.lib.post)

        messenger_vk.send_test_message('12345', 'sometext')
        assert_called_n(messenger_vk.lib.post)

    def test_send_fail(self):
        schedule_messages('text', recipients('vk', '12345'))

        def new_method(*args, **kwargs):
            raise Exception('vk failed')

        old_method = messenger_vk.lib.post
        messenger_vk.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            assert len(errors) == 1
            assert errors[0].error_log == 'vk failed'
            assert errors[0].dispatch.address == '12345'
        finally:
            messenger_vk.lib.post = old_method

