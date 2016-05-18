from mock import MagicMock, patch
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.core.management import call_command
from django.test.utils import override_settings
from django.test import TestCase
from django.test.client import RequestFactory, Client
from django.contrib.auth.models import User

try:
    from django.template.base import TemplateDoesNotExist, Template, TemplateSyntaxError
except ImportError:
    # Django 1.9+
    from django.template import TemplateDoesNotExist, Template, TemplateSyntaxError

from django.template.context import Context

from .messages.plain import PlainTextMessage
from .messages.base import MessageBase
from .models import Message, Dispatch, Subscription, DispatchError
from .toolbox import schedule_messages, recipients, send_scheduled_messages, prepare_dispatches, \
    get_user_preferences_for_ui, register_builtin_message_types, get_sitemessage_urls, \
    set_user_preferences_from_request, _ALIAS_SEP, _PREF_POST_KEY
from .messengers.base import MessengerBase
from .utils import Recipient, register_messenger_objects, \
    register_message_types, get_registered_messenger_objects, get_registered_messenger_object, \
    get_registered_message_types, override_message_type_for_app, get_message_type_for_app
from .exceptions import UnknownMessengerError, SiteMessageConfigurationError
from .signals import sig_mark_read_failed, sig_mark_read_success, sig_unsubscribe_failed, sig_unsubscribe_success

from .shortcuts import schedule_email, schedule_jabber_message, schedule_telegram_message, schedule_tweet, \
    schedule_vkontakte_message, schedule_facebook_message
from .messengers.smtp import SMTPMessenger
from .messengers.xmpp import XMPPSleekMessenger
from .messengers.twitter import TwitterMessenger
from .messengers.telegram import TelegramMessenger
from .messengers.facebook import FacebookMessenger
from .messengers.vkontakte import VKontakteMessenger


WONDERLAND_DOMAIN = '@wonderland'

urlpatterns = get_sitemessage_urls()


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

messenger_telegram = mock_thirdparty('requests', lambda: TelegramMessenger('bottoken'))
messenger_telegram.lib = MagicMock()
messenger_telegram.lib.exceptions.RequestException = MockException

messenger_fb = mock_thirdparty('requests', lambda: FacebookMessenger('pagetoken'))
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
    messenger_vk
)

register_builtin_message_types()


class TestMessenger(MessengerBase):

    title = 'Test messenger'
    alias = 'test_messenger'
    last_send = None

    def __init__(self, login, password):
        self.login = login
        self.password = password

    @classmethod
    def get_address(cls, recipient):
        if isinstance(recipient, User):
            recipient = 'user_%s' % recipient.username

        return '%s%s' % (recipient, WONDERLAND_DOMAIN)

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


class TestMessage(MessageBase):

    alias = 'test_message'
    template_ext = 'html'
    title = 'Test message type'
    supported_messengers = ['smtp', 'test_messenger']


class TestMessagePlain(PlainTextMessage):

    alias = 'testplain'
    priority = 10


class TestMessagePlainDynamic(PlainTextMessage):

    alias = 'testplain_dyn'
    has_dynamic_context = True

    @classmethod
    def compile(cls, message, messenger, dispatch=None):
        return '%s -- %s' % (message.context[MessageBase.SIMPLE_TEXT_ID], dispatch.address)


register_messenger_objects(TestMessenger('mylogin', 'mypassword'), BuggyMessenger())
register_message_types(PlainTextMessage, TestMessage, TestMessagePlain, TestMessagePlainDynamic)


class SitemessageTest(TestCase):

    def assert_called_n(self, func, n=1):
        self.assertEqual(func.call_count, n)
        func.call_count = 0

    def tearDown(self):
        User.objects.all().delete()
        Message.objects.all().delete()
        Dispatch.objects.all().delete()
        DispatchError.objects.all().delete()
        Subscription.objects.all().delete()

    @classmethod
    def render_template(cls, string, context_dict=None):
        context_dict = context_dict or {}
        return Template(string).render(Context(context_dict))


class ToolboxTest(SitemessageTest):

    def test_get_user_preferences_for_ui(self):

        user = User()
        user.save()

        messengers_titles, prefs = get_user_preferences_for_ui(user)

        self.assertEqual(len(prefs.keys()), 3)
        self.assertEqual(len(messengers_titles), 8)

        Subscription.create(user, TestMessage, TestMessenger)
        user_prefs = get_user_preferences_for_ui(
            user,
            message_filter=lambda m: m.alias == 'test_message',
            messenger_filter=lambda m: m.alias in ['smtp', 'test_messenger']
        )
        messengers_titles, prefs = user_prefs

        self.assertEqual(len(prefs.keys()), 1)
        self.assertEqual(len(messengers_titles), 2)
        self.assertIn('E-mail', messengers_titles)
        self.assertIn('Test messenger', messengers_titles)

        html = self.render_template(
            "{% load sitemessage %}{% sitemessage_prefs_table from user_prefs %}",
            {'user_prefs': user_prefs}
        )

        self.assertIn('class="sitemessage_prefs', html)
        self.assertIn('E-mail</th>', html)
        self.assertIn('Test messenger</th>', html)
        self.assertIn('Test messenger</th>', html)
        self.assertIn('value="test_message|smtp"', html)
        self.assertIn('value="test_message|test_messenger" checked', html)

        prefs_row = prefs.popitem()
        self.assertEqual(prefs_row[0], 'Test message type')
        self.assertIn(('test_message|smtp', True, False), prefs_row[1])
        self.assertIn(('test_message|test_messenger', True, True), prefs_row[1])

    def test_templatetag_fails_silent(self):
        html = self.render_template(
            "{% load sitemessage %}{% sitemessage_prefs_table from user_prefs %}",
            {'user_prefs': 'a'}
        )
        self.assertEqual(html, '')

    @override_settings(DEBUG=True)
    def test_templatetag_fails_loud(self):
        tpl = "{% load sitemessage %}{% sitemessage_prefs_table from user_prefs %}"
        context = {'user_prefs': 'a'}
        self.assertRaises(SiteMessageConfigurationError, self.render_template, tpl, context)

        tpl = "{% load sitemessage %}{% sitemessage_prefs_table user_prefs %}"
        self.assertRaises(TemplateSyntaxError, self.render_template, tpl)

    def test_send_scheduled_messages_unknown_messenger(self):
        message = Message()
        message.save()
        dispatch = Dispatch(message=message, messenger='unknownname')
        dispatch.save()

        self.assertRaises(UnknownMessengerError, send_scheduled_messages)

        send_scheduled_messages(ignore_unknown_messengers=True)

    def test_set_user_preferences_from_request(self):
        user = User()
        user.save()

        r = RequestFactory().post('/', data={_PREF_POST_KEY: 'aaa%sqqq' % _ALIAS_SEP})
        r.user = user
        set_user_preferences_from_request(r)

        subs = Subscription.objects.all()
        self.assertEqual(len(subs), 0)

        r = RequestFactory().post('/', data={_PREF_POST_KEY: 'test_message%stest_messenger' % _ALIAS_SEP})
        r.user = user
        set_user_preferences_from_request(r)

        subs = Subscription.objects.all()
        self.assertEqual(len(subs), 1)


class UtilsTest(SitemessageTest):

    def test_register_messengers(self):
        messenger = type('MyMessenger', (MessengerBase,), {})
        register_messenger_objects(messenger)
        self.assertIn(messenger.get_alias(), get_registered_messenger_objects())

    def test_register_message_types(self):
        message = type('MyMessage', (MessageBase,), {})
        register_message_types(message)
        self.assertIn(message.get_alias(), get_registered_message_types())

    def test_recipients(self):
        user = User(username='myuser')
        to = ('gogi', 'givi', user)

        r1 = recipients('test_messenger', to)

        self.assertEqual(len(r1), len(to))
        self.assertEqual(r1[0].address, 'gogi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[0].messenger, 'test_messenger')
        self.assertEqual(r1[1].address, 'givi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[1].messenger, 'test_messenger')
        self.assertEqual(r1[2].address, 'user_myuser%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[2].messenger, 'test_messenger')

    def test_prepare_undispatched(self):
        m, d = Message.create('testplain', {MessageBase.SIMPLE_TEXT_ID: 'abc'})

        Subscription.create('fred', 'testplain', 'test_messenger')
        Subscription.create('colon', 'testplain', 'test_messenger')

        dispatches = prepare_dispatches()
        self.assertEqual(len(dispatches), 2)
        self.assertEqual(dispatches[0].address, 'fred')
        self.assertEqual(dispatches[1].address, 'colon')

    def test_send_scheduled_messages(self):
        # This one won't count, as won't fit into message priority filter.
        schedule_messages(TestMessagePlainDynamic('my_dyn_msg'), recipients('test_messenger', ('three', 'four')))

        msgr = get_registered_messenger_object('test_messenger')
        msg = TestMessagePlain('my_message')
        schedule_messages(msg, recipients(msgr, ('one', 'two')))
        send_scheduled_messages(priority=TestMessagePlain.priority)
        self.assertEqual(len(msgr.last_send['dispatch_models']), 2)
        self.assertEqual(msgr.last_send['message_model'].cls, 'testplain')
        self.assertEqual(msgr.last_send['message_cls'], TestMessagePlain)
        self.assertEqual(msgr.last_send['dispatch_models'][0].message_cache, 'my_message')
        self.assertEqual(msgr.last_send['dispatch_models'][1].message_cache, 'my_message')

    def test_send_scheduled_messages_dynamic_context(self):
        msgr = get_registered_messenger_object('test_messenger')
        msg_dyn = TestMessagePlainDynamic('my_dyn_msg')
        schedule_messages(msg_dyn, recipients(msgr, ('three', 'four')))
        send_scheduled_messages()
        self.assertEqual(len(msgr.last_send['dispatch_models']), 2)
        self.assertEqual(msgr.last_send['message_model'].cls, 'testplain_dyn')
        self.assertEqual(msgr.last_send['message_cls'], TestMessagePlainDynamic)
        self.assertEqual(msgr.last_send['dispatch_models'][0].message_cache, 'my_dyn_msg -- three%s' % WONDERLAND_DOMAIN)
        self.assertEqual(msgr.last_send['dispatch_models'][1].message_cache, 'my_dyn_msg -- four%s' % WONDERLAND_DOMAIN)

    def test_schedule_message(self):
        msg = TestMessagePlain('schedule_func')
        model, _ = schedule_messages(msg)[0]
        self.assertEqual(model.cls, msg.get_alias())
        self.assertEqual(model.context, msg.get_context())
        self.assertEqual(model.priority, TestMessagePlain.priority)
        self.assertFalse(model.dispatches_ready)

        msg = TestMessagePlain('schedule_func')
        model, _ = schedule_messages(msg, priority=33)[0]
        self.assertEqual(model.cls, msg.get_alias())
        self.assertEqual(model.context, msg.get_context())
        self.assertEqual(model.priority, 33)
        self.assertFalse(model.dispatches_ready)

        user = User()
        user.save()

        model, dispatch_models = schedule_messages('simple message', recipients('test_messenger', ('gogi', 'givi')), sender=user)[0]

        self.assertEqual(model.cls, 'plain')
        self.assertEqual(model.context, {'use_tpl': False, MessageBase.SIMPLE_TEXT_ID: 'simple message', 'tpl': None})
        self.assertEqual(model.sender, user)
        self.assertTrue(model.dispatches_ready)

        self.assertEqual(len(dispatch_models), 2)
        self.assertEqual(dispatch_models[0].address, 'gogi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(dispatch_models[0].messenger, 'test_messenger')

    def test_override_message_type_for_app(self):

        mt = get_message_type_for_app('myapp', 'testplain')
        self.assertIs(mt, TestMessagePlain)

        override_message_type_for_app('myapp', 'sometype', 'test_message')
        mt = get_message_type_for_app('myapp', 'sometype')
        self.assertIs(mt, TestMessage)


class SubscriptionModelTest(SitemessageTest):

    def test_create(self):

        s = Subscription.create('abc', 'message', 'messenger')

        self.assertIsNotNone(s.time_created)
        self.assertIsNone(s.recipient)
        self.assertEqual(s.address, 'abc')
        self.assertEqual(s.message_cls, 'message')
        self.assertEqual(s.messenger_cls, 'messenger')

        s = Subscription.create(1, 'message', 'messenger')

        self.assertIsNotNone(s.time_created)
        self.assertIsNone(s.address)
        self.assertEqual(s.recipient_id, 1)
        self.assertEqual(s.message_cls, 'message')
        self.assertEqual(s.messenger_cls, 'messenger')

    def test_cancel(self):

        Subscription.create('abc', 'message', 'messenger')
        Subscription.create('abc', 'message1', 'messenger')
        Subscription.create('abc', 'message', 'messenger1')
        self.assertEqual(
            Subscription.objects.filter(address='abc').count(), 3
        )

        Subscription.cancel('abc', 'message', 'messenger')
        self.assertEqual(
            Subscription.objects.filter(address='abc').count(), 2
        )

        Subscription.create(1, 'message', 'messenger')
        self.assertEqual(
            Subscription.objects.filter(recipient=1).count(), 1
        )

        Subscription.cancel(1, 'message', 'messenger')
        self.assertEqual(
            Subscription.objects.filter(recipient=1).count(), 0
        )

    def test_replace_for_user(self):
        new_prefs = [('message3', 'messenger3')]
        user = User()

        r = Subscription.replace_for_user(user, new_prefs)

        user.save()

        Subscription.create(user, 'message', 'messenger')
        Subscription.create(user, 'message2', 'messenger2')

        self.assertEqual(Subscription.get_for_user(user).count(), 2)

        Subscription.replace_for_user(user, new_prefs)

        s = Subscription.get_for_user(user)
        self.assertEqual(s.count(), 1)
        s = s[0]
        self.assertEqual(s.message_cls, 'message3')
        self.assertEqual(s.messenger_cls, 'messenger3')

    def test_get_for_user(self):
        user = User()

        r = Subscription.get_for_user(user)
        self.assertEqual(r, [])

        user.save()

        self.assertEqual(Subscription.get_for_user(user).count(), 0)

        Subscription.create(user, 'message', 'messenger')

        self.assertEqual(Subscription.get_for_user(user).count(), 1)

    def test_get_for_message_cls(self):
        self.assertEqual(Subscription.get_for_message_cls('mymsg').count(), 0)

        Subscription.create('aaa', 'mymsg', 'messenger')
        Subscription.create('bbb', 'mymsg', 'messenger2')

        self.assertEqual(Subscription.get_for_message_cls('mymsg').count(), 2)

    def test_str(self):
        s = Subscription()
        s.address = 'aaa'

        self.assertIn('aaa', str(s))


class DispatchErrorModelTest(SitemessageTest):

    def test_str(self):
        e = DispatchError()
        e.dispatch_id = 444

        self.assertIn('444', str(e))


class DispatchModelTest(SitemessageTest):

    def test_create(self):

        message = Message(cls='test_message')
        message.save()

        user = User(username='u')
        user.save()

        recipients_ = recipients('test_messenger', [user])
        recipients_ += recipients('buggy', 'idle')

        dispatches = Dispatch.create(message, recipients_)
        self.assertTrue(isinstance(dispatches[0], Dispatch))
        self.assertTrue(isinstance(dispatches[1], Dispatch))
        self.assertEqual(dispatches[0].message_id, message.id)
        self.assertEqual(dispatches[1].message_id, message.id)
        self.assertEqual(dispatches[0].messenger, 'test_messenger')
        self.assertEqual(dispatches[1].messenger, 'buggy')

        dispatches = Dispatch.create(message, Recipient('msgr', None, 'address'))
        self.assertEqual(len(dispatches), 1)

    def test_log_dispatches_errors(self):

        self.assertEqual(DispatchError.objects.count(), 0)

        d1 = Dispatch(message_id=1)
        d1.save()

        d1.error_log = 'some_text'

        Dispatch.log_dispatches_errors([d1])
        self.assertEqual(DispatchError.objects.count(), 1)
        self.assertEqual(DispatchError.objects.get(pk=1).error_log, 'some_text')

    def test_get_unread(self):

        d1 = Dispatch(message_id=1)
        d1.save()

        d2 = Dispatch(message_id=1)
        d2.save()
        self.assertEqual(Dispatch.get_unread().count(), 2)

        d2.read_status = Dispatch.READ_STATUS_READ
        d2.save()
        self.assertEqual(Dispatch.get_unread().count(), 1)

    def test_set_dispatches_statuses(self):

        d = Dispatch(message_id=1)
        d.save()

        Dispatch.set_dispatches_statuses(**{'sent': [d]})
        d_ = Dispatch.objects.get(pk=d.id)
        self.assertEqual(d_.dispatch_status, Dispatch.DISPATCH_STATUS_SENT)
        self.assertEqual(d_.retry_count, 1)

        Dispatch.set_dispatches_statuses(**{'error': [d]})
        d_ = Dispatch.objects.get(pk=d.id)
        self.assertEqual(d_.dispatch_status, Dispatch.DISPATCH_STATUS_ERROR)
        self.assertEqual(d_.retry_count, 2)

    def test_str(self):
        d = Dispatch()
        d.address = 'tttt'

        self.assertIn('tttt', str(d))

    def test_mark_read(self):
        d = Dispatch()
        self.assertEqual(d.read_status, d.READ_STATUS_UNDREAD)
        d.mark_read()
        self.assertEqual(d.read_status, d.READ_STATUS_READ)


class MessageModelTest(SitemessageTest):

    def test_create(self):
        user = User(username='u')
        user.save()

        m, _ = Message.create('some', {'abc': 'abc'}, sender=user, priority=22)
        self.assertEqual(m.cls, 'some')
        self.assertEqual(m.context, {'abc': 'abc'})
        self.assertEqual(m.sender, user)
        self.assertEqual(m.priority, 22)
        self.assertFalse(m.dispatches_ready)

        ctx = {'a': 'a', 'b': 'b'}
        m, _ = Message.create('some2', ctx)
        self.assertEqual(m.cls, 'some2')
        self.assertEqual(m.context, ctx)
        self.assertIsNone(m.sender)
        self.assertFalse(m.dispatches_ready)

    def test_deserialize_context(self):
        m = Message(cls='some_cls', context={'a': 'a', 'b': 'b', 'c': 'c'})
        m.save()

        m2 = Message.objects.get(pk=m.pk)
        self.assertEquals(m2.context, {'a': 'a', 'b': 'b', 'c': 'c'})

    def test_get_type(self):
        m = Message(cls='test_message')

        self.assertIs(m.get_type(), TestMessage)

    def test_str(self):
        m = Message()
        m.cls = 'aaa'

        self.assertEqual(str(m), 'aaa')


class MessengerTest(SitemessageTest):

    def test_init_params(self):
        messengers = get_registered_messenger_objects()
        my = messengers['test_messenger']
        self.assertEqual(my.login, 'mylogin')
        self.assertEqual(my.password, 'mypassword')

    def test_alias(self):
        messenger = type('MyMessenger', (MessengerBase,), {'alias': 'myalias'})
        self.assertEqual(messenger.get_alias(), 'myalias')

        messenger = type('MyMessenger', (MessengerBase,), {})
        self.assertEqual(messenger.get_alias(), 'MyMessenger')

    def test_get_recipients_data(self):
        user = User(username='myuser')
        to = ('gogi', 'givi', user)

        r1 = TestMessenger._structure_recipients_data(to)

        self.assertEqual(len(r1), len(to))
        self.assertEqual(r1[0].address, 'gogi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[0].messenger, 'test_messenger')
        self.assertEqual(r1[1].address, 'givi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[1].messenger, 'test_messenger')
        self.assertEqual(r1[2].address, 'user_myuser%s' % WONDERLAND_DOMAIN)
        self.assertEqual(r1[2].messenger, 'test_messenger')

    def test_send(self):
        m = TestMessenger('l', 'p')
        m.send('message_cls', 'message_model', 'dispatch_models')

        self.assertEqual(m.last_send['message_cls'], 'message_cls')
        self.assertEqual(m.last_send['message_model'], 'message_model')
        self.assertEqual(m.last_send['dispatch_models'], 'dispatch_models')

        m = BuggyMessenger()
        recipiets_ = recipients('test_messenger', ['a', 'b', 'c', 'd'])
        self.assertRaises(Exception, m.send, 'a buggy message', recipiets_)


class ShortcutsTest(SitemessageTest):

    def test_schedule_email(self):
        schedule_email('some text', 'some@one.here')

        self.assertEqual(Message.objects.all()[0].cls, 'email_plain')
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Dispatch.objects.count(), 1)

        schedule_email({'header': 'one', 'body': 'two'}, 'some@one.here')

        self.assertEqual(Message.objects.all()[1].cls, 'email_html')
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Dispatch.objects.count(), 2)

    def test_schedule_jabber_message(self):
        schedule_jabber_message('message', 'noone')

    def test_schedule_tweet(self):
        schedule_tweet('message', '')

    def test_schedule_tele(self):
        schedule_telegram_message('message', '')

    def test_schedule_fb(self):
        schedule_facebook_message('message')

    def test_schedule_vk(self):
        schedule_vkontakte_message('message', '12345')


class SMTPMessengerTest(SitemessageTest):

    def test_get_address(self):
        r = object()
        self.assertEqual(messenger_smtp.get_address(r), r)

        r = type('r', (object,), dict(email='somewhere'))
        self.assertEqual(messenger_smtp.get_address(r), 'somewhere')

    def test_send(self):
        schedule_messages('text', recipients('smtp', 'someone'))
        send_scheduled_messages()
        self.assert_called_n(messenger_smtp.smtp.sendmail)

    def test_send_fail(self):
        schedule_messages('text', recipients('smtp', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('smtp failed')

        old_method = messenger_smtp.smtp.sendmail
        messenger_smtp.smtp.sendmail = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'smtp failed')
            self.assertEqual(errors[0].dispatch.address, 'someone')
        finally:
            messenger_smtp.smtp.sendmail = old_method

    def test_send_test_message(self):
        messenger_smtp.send_test_message('someone', 'sometext')
        self.assert_called_n(messenger_smtp.smtp.sendmail)


class TwitterMessengerTest(SitemessageTest):

    def test_get_address(self):
        r = object()
        self.assertEqual(messenger_twitter.get_address(r), r)

        r = type('r', (object,), dict(twitter='somewhere'))
        self.assertEqual(messenger_twitter.get_address(r), 'somewhere')

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
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'tweet failed')
            self.assertEqual(errors[0].dispatch.address, 'someone')
        finally:
            messenger_twitter.api.statuses.update = old_method


class XMPPSleekMessengerTest(SitemessageTest):

    def test_get_address(self):
        r = object()
        self.assertEqual(messenger_xmpp.get_address(r), r)

        r = type('r', (object,), dict(jabber='somewhere'))
        self.assertEqual(messenger_xmpp.get_address(r), 'somewhere')

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
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'xmppsleek failed')
            self.assertEqual(errors[0].dispatch.address, 'someone')
        finally:
            messenger_xmpp.xmpp.send_message = old_method


class TelegramMessengerTest(SitemessageTest):

    def setUp(self):
        messenger_telegram._verify_bot()
        messenger_telegram.lib.post.call_count = 0

    def test_get_address(self):
        r = object()
        self.assertEqual(messenger_telegram.get_address(r), r)

        r = type('r', (object,), dict(telegram='chat_id'))
        self.assertEqual(messenger_telegram.get_address(r), 'chat_id')

    def test_send(self):
        schedule_messages('text', recipients('telegram', '1234567'))
        send_scheduled_messages()
        self.assert_called_n(messenger_telegram.lib.post)

    def test_send_test_message(self):
        messenger_telegram.send_test_message('someone', 'sometext')
        self.assert_called_n(messenger_telegram.lib.post)

        messenger_telegram.send_test_message('', 'sometext')
        self.assert_called_n(messenger_telegram.lib.post)

    def test_get_chat_ids(self):
        self.assertEqual(messenger_telegram.get_chat_ids(), [])
        self.assert_called_n(messenger_telegram.lib.post, 2)

    def test_send_fail(self):
        schedule_messages('text', recipients('telegram', 'someone'))

        def new_method(*args, **kwargs):
            raise Exception('telegram failed')

        old_method = messenger_telegram.lib.post
        messenger_telegram.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'telegram failed')
            self.assertEqual(errors[0].dispatch.address, 'someone')
        finally:
            messenger_telegram.lib.post = old_method


class FacebookMessengerTest(SitemessageTest):

    def setUp(self):
        messenger_fb.lib.post.call_count = 0
        messenger_fb.lib.get.call_count = 0

    def test_send(self):
        schedule_messages('text', recipients('fb', ''))
        send_scheduled_messages()
        self.assert_called_n(messenger_fb.lib.post)

    def test_send_test_message(self):
        messenger_fb.send_test_message('', 'sometext')
        self.assert_called_n(messenger_fb.lib.post)

        messenger_fb.send_test_message('', 'sometext')
        self.assert_called_n(messenger_fb.lib.post)

    def test_get_page_access_token(self):
        self.assertEqual(messenger_fb.get_page_access_token('app_id', 'app_secret', 'user_token'), {})
        self.assert_called_n(messenger_fb.lib.get, 2)

    def test_send_fail(self):
        schedule_messages('text', recipients('fb', ''))

        def new_method(*args, **kwargs):
            raise Exception('fb failed')

        old_method = messenger_fb.lib.post
        messenger_fb.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'fb failed')
            self.assertEqual(errors[0].dispatch.address, '')
        finally:
            messenger_fb.lib.post = old_method


class VKontakteMessengerTest(SitemessageTest):

    def setUp(self):
        messenger_vk.lib.post.call_count = 0
        messenger_vk.lib.get.call_count = 0

    def test_send(self):
        schedule_messages('text', recipients('vk', '12345'))
        send_scheduled_messages()
        self.assert_called_n(messenger_vk.lib.post)

    def test_send_test_message(self):
        messenger_vk.send_test_message('12345', 'sometext')
        self.assert_called_n(messenger_vk.lib.post)

        messenger_vk.send_test_message('12345', 'sometext')
        self.assert_called_n(messenger_vk.lib.post)

    def test_send_fail(self):
        schedule_messages('text', recipients('vk', '12345'))

        def new_method(*args, **kwargs):
            raise Exception('vk failed')

        old_method = messenger_vk.lib.post
        messenger_vk.lib.post = new_method

        try:
            send_scheduled_messages()
            errors = DispatchError.objects.all()
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_log, 'vk failed')
            self.assertEqual(errors[0].dispatch.address, '12345')
        finally:
            messenger_vk.lib.post = old_method

class ViewsTest(SitemessageTest):

    STATUS_SUCCESS = 'success'
    STATUS_FAIL = 'fail'

    def setUp(self):

        def catcher_success(*args, **kwargs):
            self.status = self.STATUS_SUCCESS
        self.catcher_success = catcher_success

        def catcher_fail(*args, **kwargs):
            self.status = self.STATUS_FAIL
        self.catcher_fail = catcher_fail

        user = User()
        user.save()
        self.user = user

        msg_type = TestMessagePlain('sometext')
        self.msg_type = msg_type

        msg_model, _ = schedule_messages(msg_type, recipients(TestMessenger, user))[0]
        dispatch = Dispatch.objects.all()[0]
        self.msg_model = msg_model
        self.dispatch = dispatch

        dispatch_hash = msg_type.get_dispatch_hash(dispatch.id, msg_model.id)
        self.dispatch_hash = dispatch_hash

    def send_request(self, msg_id, dispatch_id, dispatch_hash, expected_status):
        Client().get(reverse(self.view_name, args=[msg_id, dispatch_id, dispatch_hash]))
        self.assertEqual(self.status, expected_status)
        self.status = None

    def generic_view_test(self):
        # Unknown dispatch ID.
        self.send_request(self.msg_model.id, 999999, self.dispatch_hash, self.STATUS_FAIL)
        # Invalid hash.
        self.send_request(self.msg_model.id, self.dispatch.id, 'nothash', self.STATUS_FAIL)
        # Message ID mismatch.
        self.send_request(999999, self.dispatch.id, self.dispatch_hash, self.STATUS_FAIL)

    def test_unsubscribe(self):
        self.view_name = 'sitemessage_unsubscribe'

        sig_unsubscribe_success.connect(self.catcher_success, weak=False)
        sig_unsubscribe_failed.connect(self.catcher_fail, weak=False)

        self.generic_view_test()

        subscr = Subscription(
            message_cls=self.msg_type, messenger_cls=TestMessenger.alias, recipient=self.user
        )
        subscr.save()
        self.assertEqual(len(Subscription.objects.all()), 1)

        self.send_request(self.msg_model.id, self.dispatch.id, self.dispatch_hash, self.STATUS_SUCCESS)
        self.assertEqual(len(Subscription.objects.all()), 0)

    def test_mark_read(self):

        self.view_name = 'sitemessage_mark_read'

        sig_mark_read_success.connect(self.catcher_success, weak=False)
        sig_mark_read_failed.connect(self.catcher_fail, weak=False)

        self.generic_view_test()
        self.assertFalse(Dispatch.objects.get(pk=self.dispatch.pk).is_read())

        self.send_request(self.msg_model.id, self.dispatch.id, self.dispatch_hash, self.STATUS_SUCCESS)
        self.assertTrue(Dispatch.objects.get(pk=self.dispatch.pk).is_read())


class MessageTest(SitemessageTest):

    def test_alias(self):
        message = type('MyMessage', (MessageBase,), {'alias': 'myalias'})
        self.assertEqual(message.get_alias(), 'myalias')

        message = type('MyMessage', (MessageBase,), {})
        self.assertEqual(message.get_alias(), 'MyMessage')

        message = message()
        self.assertEqual(str(message), 'MyMessage')

    def test_context(self):
        msg = TestMessage({'title': 'My message!', 'name': 'idle'})
        self.assertEqual(msg.context, {'name': 'idle', 'title': 'My message!', 'tpl': None, 'use_tpl': True})

    def test_get_template(self):
        self.assertEqual(
            TestMessage.get_template(TestMessage(), TestMessenger('a', 'b')),
            'sitemessage/messages/test_message__test_messenger.html'
        )

    def test_compile_string(self):
        msg = TestMessagePlain('simple')
        self.assertEqual(TestMessagePlain.compile(msg, TestMessenger('a', 'b')), 'simple')

    def test_compile_dict(self):
        msg = TestMessage({'title': 'My message!', 'name': 'idle'})
        self.assertRaises(TemplateDoesNotExist, TestMessage.compile, msg, TestMessenger('a', 'b'))

    def test_schedule(self):
        msg = TestMessagePlain('schedule1')
        model, _ = msg.schedule()
        self.assertEqual(model.cls, msg.get_alias())
        self.assertEqual(model.context, msg.get_context())
        self.assertIsNone(model.sender)

        user = User()
        user.save()

        msg = TestMessagePlain('schedule2')
        model, _ = msg.schedule(sender=user)
        self.assertEqual(model.sender, user)


class CommandsTest(SitemessageTest):

    def test_send_scheduled(self):
        call_command('sitemessage_send_scheduled', priority=1)


@override_settings(EMAIL_BACKEND='sitemessage.backends.EmailBackend')
class BackendsTest(SitemessageTest):

    def test_email_backend(self):
        send_mail('subj', 'message', 'from@example.com', ['to@example.com'], fail_silently=False)
        dispatches = list(Dispatch.objects.all())
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(dispatches[0].messenger, 'smtp')
        self.assertEqual(dispatches[0].address, 'to@example.com')
        self.assertEqual(dispatches[0].dispatch_status, Dispatch.DISPATCH_STATUS_PENDING)
        self.assertEqual(dispatches[0].message.cls, 'email_html')
        self.assertEqual(dispatches[0].message.context['subject'], 'subj')
        self.assertEqual(dispatches[0].message.context['contents'], 'message')
