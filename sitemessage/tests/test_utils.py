from sitemessage.messages.base import MessageBase
from sitemessage.messengers.base import MessengerBase
from sitemessage.models import Message, Subscription
from sitemessage.toolbox import schedule_messages, recipients, send_scheduled_messages, prepare_dispatches
from sitemessage.utils import register_message_types, register_messenger_objects, \
    get_registered_messenger_objects, get_registered_messenger_object, get_registered_message_types, \
    override_message_type_for_app, get_message_type_for_app

from .testapp.sitemessages import WONDERLAND_DOMAIN, MessagePlainForTest, MessagePlainDynamicForTest, MessageForTest, \
    MessengerForTest


def test_register_messengers():
    messenger = type('MyMessenger', (MessengerBase,), {})  # type: MessengerBase
    register_messenger_objects(messenger)
    assert messenger.get_alias() in get_registered_messenger_objects()


def test_register_message_types():
    message = type('MyMessage', (MessageBase,), {})  # type: MessageBase
    register_message_types(message)
    assert message.get_alias() in get_registered_message_types()


def test_recipients(user_create):
    user = user_create(attributes=dict(username='myuser'))
    to = ['gogi', 'givi', user]

    r1 = recipients('test_messenger', to)

    assert len(r1) == len(to)
    assert r1[0].address == f'gogi{WONDERLAND_DOMAIN}'
    assert r1[0].messenger == 'test_messenger'
    assert r1[1].address == f'givi{WONDERLAND_DOMAIN}'
    assert r1[1].messenger == 'test_messenger'
    assert r1[2].address == f'user_myuser{WONDERLAND_DOMAIN}'
    assert r1[2].messenger == 'test_messenger'


def test_prepare_undispatched():
    m, d = Message.create('testplain', {MessageBase.SIMPLE_TEXT_ID: 'abc'})

    Subscription.create('fred', 'testplain', 'test_messenger')
    Subscription.create('colon', 'testplain', 'test_messenger')

    dispatches = prepare_dispatches()
    assert len(dispatches) == 2
    assert dispatches[0].address == 'fred'
    assert dispatches[1].address == 'colon'


def test_send_scheduled_messages():
    # This one won't count, as won't fit into message priority filter.
    schedule_messages(
        MessagePlainDynamicForTest('my_dyn_msg'),
        recipients('test_messenger', ['three', 'four']))

    msgr = get_registered_messenger_object('test_messenger')  # type: MessengerForTest
    msg = MessagePlainForTest('my_message')
    schedule_messages(msg, recipients(msgr, ['one', 'two']))
    send_scheduled_messages(priority=MessagePlainForTest.priority)

    assert len(msgr.last_send['dispatch_models']) == 2
    assert msgr.last_send['message_model'].cls == 'testplain'
    assert msgr.last_send['message_cls'] == MessagePlainForTest
    assert msgr.last_send['dispatch_models'][0].message_cache == 'my_message'
    assert msgr.last_send['dispatch_models'][1].message_cache == 'my_message'


def test_send_scheduled_messages_dynamic_context():
    msgr = get_registered_messenger_object('test_messenger')  # type: MessengerForTest
    msg_dyn = MessagePlainDynamicForTest('my_dyn_msg')
    schedule_messages(msg_dyn, recipients(msgr, ['three', 'four']))
    send_scheduled_messages()

    assert len(msgr.last_send['dispatch_models']) == 2
    assert msgr.last_send['message_model'].cls == 'testplain_dyn'
    assert msgr.last_send['message_cls'] == MessagePlainDynamicForTest
    assert msgr.last_send['dispatch_models'][0].message_cache == f'my_dyn_msg -- three{WONDERLAND_DOMAIN}'
    assert msgr.last_send['dispatch_models'][1].message_cache == f'my_dyn_msg -- four{WONDERLAND_DOMAIN}'


def test_schedule_message(user):
    msg = MessagePlainForTest('schedule_func')
    model, _ = schedule_messages(msg)[0]

    assert model.cls == msg.get_alias()
    assert model.context == msg.get_context()
    assert model.priority == MessagePlainForTest.priority
    assert not model.dispatches_ready

    msg = MessagePlainForTest('schedule_func')
    model, _ = schedule_messages(msg, priority=33)[0]

    assert model.cls == msg.get_alias()
    assert model.context == msg.get_context()
    assert model.priority == 33
    assert not model.dispatches_ready

    model, dispatch_models = \
    schedule_messages(
        'simple message',
        recipients('test_messenger', ['gogi', 'givi']), sender=user)[0]

    assert model.cls == 'plain'
    assert model.context == {'use_tpl': False, MessageBase.SIMPLE_TEXT_ID: 'simple message', 'tpl': None}
    assert model.sender == user
    assert model.dispatches_ready

    assert len(dispatch_models) == 2
    assert dispatch_models[0].address == f'gogi{WONDERLAND_DOMAIN}'
    assert dispatch_models[0].messenger == 'test_messenger'


def test_override_message_type_for_app():
    mt = get_message_type_for_app('myapp', 'testplain')
    assert mt is MessagePlainForTest

    override_message_type_for_app('myapp', 'sometype', 'test_message')
    mt = get_message_type_for_app('myapp', 'sometype')
    assert mt is MessageForTest
