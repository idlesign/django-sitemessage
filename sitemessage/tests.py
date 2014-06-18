from django.utils import unittest
from django.contrib.auth.models import User
from django.template.base import TemplateDoesNotExist
from django.db.utils import IntegrityError

from .messages import PlainTextMessage
from .models import Message, Dispatch
from .toolbox import schedule_messages, recipients, send_scheduled_messages, prepare_dispatches
from .utils import MessageBase, MessengerBase, Recipient, register_messenger_objects, \
    register_message_types, get_registered_messenger_objects, get_registered_messenger_object, \
    get_registered_message_types
from .exceptions import MessengerWarmupException


# TODO More tests, please %)

WONDERLAND_DOMAIN = '@wonderland'


class TestMessenger(MessengerBase):

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

    alias = 'buggy'

    def send(self, message_cls, message_model, dispatch_models):
        raise Exception('Damn it.')


class TestMessage(MessageBase):

    alias = 'test_message'
    template_ext = 'html'


class TestMessagePlain(PlainTextMessage):

    alias = 'testplain'
    priority = 10

    @classmethod
    def calculate_recipients(cls, message):
        return recipients('test_messenger', ('fred', 'colon'))


class TestMessagePlainDynamic(PlainTextMessage):

    alias = 'testplain_dyn'
    has_dynamic_context = True

    @classmethod
    def compile(cls, message, messenger, dispatch=None):
        return '%s -- %s' % (message.context[MessageBase.SIMPLE_TEXT_ID], dispatch.address)


register_messenger_objects(TestMessenger('mylogin', 'mypassword'), BuggyMessenger())
register_message_types(PlainTextMessage, TestMessage, TestMessagePlain, TestMessagePlainDynamic)


class UtilityTest(unittest.TestCase):

    def setUp(self):
        Message.objects.all().delete()

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
        dispatches = prepare_dispatches()
        self.assertEqual(len(dispatches), 2)
        self.assertEqual(dispatches[0].address, 'fred%s' % WONDERLAND_DOMAIN)
        self.assertEqual(dispatches[1].address, 'colon%s' % WONDERLAND_DOMAIN)

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

        model, dispatch_models = schedule_messages('simple message', recipients('test_messenger', ('gogi', 'givi')), sender=user)[0]

        self.assertEqual(model.cls, 'plain')
        self.assertEqual(model.context, {'use_tpl': False, MessageBase.SIMPLE_TEXT_ID: 'simple message', 'tpl': None})
        self.assertEqual(model.sender, user)
        self.assertTrue(model.dispatches_ready)

        self.assertEqual(len(dispatch_models), 2)
        self.assertEqual(dispatch_models[0].address, 'gogi%s' % WONDERLAND_DOMAIN)
        self.assertEqual(dispatch_models[0].messenger, 'test_messenger')


class DispatchModelTest(unittest.TestCase):

    def test_create(self):

        message = Message(cls='test_message')
        message.save()

        user = User(username='u')

        recipients_ = recipients('test_messenger', [user])
        recipients_ += recipients('buggy', 'idle')

        dispatches = Dispatch.create(message, recipients_)
        self.assertTrue(isinstance(dispatches[0], Dispatch))
        self.assertTrue(isinstance(dispatches[1], Dispatch))
        self.assertEqual(dispatches[0].message_id, message.id)
        self.assertEqual(dispatches[1].message_id, message.id)
        self.assertEqual(dispatches[0].messenger, 'test_messenger')
        self.assertEqual(dispatches[1].messenger, 'buggy')


class MessageModelTest(unittest.TestCase):

    def test_create(self):
        user = User(username='u')

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


class MessengerTest(unittest.TestCase):

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


class MessageTest(unittest.TestCase):

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
        msg = TestMessagePlain('schedule2')
        model, _ = msg.schedule(sender=user)
        self.assertEqual(model.sender, user)
