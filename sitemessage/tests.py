from django.utils import unittest
from django.contrib.auth.models import User
from django.template.base import TemplateDoesNotExist
from django.db.utils import IntegrityError

from .messages import PlainTextMessage
from .models import Message, Dispatch, Subscription, DispatchError
from .toolbox import schedule_messages, recipients, send_scheduled_messages, prepare_dispatches, \
    get_user_preferences_for_ui
from .utils import MessageBase, MessengerBase, Recipient, register_messenger_objects, \
    register_message_types, get_registered_messenger_objects, get_registered_messenger_object, \
    get_registered_message_types
from .exceptions import MessengerWarmupException, UnknownMessengerError, UnknownMessageTypeError
from .schortcuts import schedule_email, schedule_jabber_message
from .messengers.smtp import SMTPMessenger
from .messengers.xmpp import XMPPSleekMessenger
from .messengers.twitter import TwitterMessenger


WONDERLAND_DOMAIN = '@wonderland'


register_messenger_objects(
    SMTPMessenger(),
    XMPPSleekMessenger('somjid', 'somepasswd'),
    TwitterMessenger('key', 'secret', 'token', 'token_secret')
)


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


class SitemessageTest(unittest.TestCase):

    def tearDown(self):
        User.objects.all().delete()
        Message.objects.all().delete()
        Dispatch.objects.all().delete()
        Subscription.objects.all().delete()


class ToolboxTest(SitemessageTest):

    def test_get_user_preferences_for_ui(self):

        user = User()
        user.save()

        messengers_titles, prefs = get_user_preferences_for_ui(user)

        self.assertEqual(len(prefs.keys()), 2)
        self.assertEqual(len(messengers_titles), 5)

        Subscription.create(user, TestMessage, TestMessenger)
        messengers_titles, prefs = get_user_preferences_for_ui(
            user,
            message_filter=lambda m: m.alias == 'test_message',
            messenger_filter=lambda m: m.alias in ['smtp', 'test_messenger']
        )

        self.assertEqual(len(prefs.keys()), 1)
        self.assertEqual(len(messengers_titles), 2)
        self.assertIn('E-mail', messengers_titles)
        self.assertIn('Test messenger', messengers_titles)

        prefs_row = prefs.popitem()
        self.assertEqual(prefs_row[0], 'Test message type')
        self.assertIn(('test_message|smtp', True, False), prefs_row[1])
        self.assertIn(('test_message|test_messenger', True, True), prefs_row[1])


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

        self.assertEqual(Message.objects.get(pk=1).cls, 'email_plain')
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Dispatch.objects.count(), 1)

        schedule_email({'header': 'one', 'body': 'two'}, 'some@one.here')

        self.assertEqual(Message.objects.get(pk=2).cls, 'email_html')
        self.assertEqual(Message.objects.count(), 2)
        self.assertEqual(Dispatch.objects.count(), 2)

    def test_schedule_jabber_message(self):
        schedule_jabber_message('message', 'noone')


class MessageTest(SitemessageTest):

    def test_alias(self):
        message = type('MyMessage', (MessageBase,), {'alias': 'myalias'})
        self.assertEqual(message.get_alias(), 'myalias')

        message = type('MyMessage', (MessengerBase,), {})
        self.assertEqual(message.get_alias(), 'MyMessage')

    def test_context(self):
        msg = TestMessage({'title': 'My message!', 'name': 'idle'})
        self.assertEqual(msg.context, {'name': 'idle', 'title': 'My message!', 'tpl': None, 'use_tpl': True})

    def test_get_template(self):
        self.assertEqual(TestMessage.get_template(TestMessage(), TestMessenger('a', 'b')), 'sitemessage/test_message_test_messenger.html')

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
