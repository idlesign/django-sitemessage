from sitemessage.models import Message, Dispatch, Subscription, DispatchError
from sitemessage.toolbox import recipients
from sitemessage.utils import Recipient

from .testapp.sitemessages import MessageForTest


class TestSubscriptionModel(object):

    def test_create(self, user):

        s = Subscription.create('abc', 'message', 'messenger')

        assert s.time_created is not None
        assert s.recipient is None
        assert s.address == 'abc'
        assert s.message_cls == 'message'
        assert s.messenger_cls == 'messenger'

        s = Subscription.create(user, 'message', 'messenger')

        assert s.time_created is not None
        assert s.address is None
        assert s.recipient_id == user.id
        assert s.message_cls == 'message'
        assert s.messenger_cls == 'messenger'

    def test_cancel(self, user):

        Subscription.create('abc', 'message', 'messenger')
        Subscription.create('abc', 'message1', 'messenger')
        Subscription.create('abc', 'message', 'messenger1')
        assert Subscription.objects.filter(address='abc').count() == 3
        
        Subscription.cancel('abc', 'message', 'messenger')
        assert Subscription.objects.filter(address='abc').count() == 2

        Subscription.create(user, 'message', 'messenger')
        assert Subscription.objects.filter(recipient=user).count() == 1
        
        Subscription.cancel(user, 'message', 'messenger')
        assert Subscription.objects.filter(recipient=user).count() == 0
        
    def test_replace_for_user(self, user):
        new_prefs = [('message3', 'messenger3')]

        assert Subscription.replace_for_user(user, new_prefs)

        Subscription.create(user, 'message', 'messenger')
        Subscription.create(user, 'message2', 'messenger2')

        assert Subscription.get_for_user(user).count() == 3

        Subscription.replace_for_user(user, new_prefs)

        s = Subscription.get_for_user(user)
        assert s.count() == 1
        s = s[0]
        assert s.message_cls == 'message3'
        assert s.messenger_cls == 'messenger3'

    def test_get_for_user(self, user):
        r = Subscription.get_for_user(user)
        assert list(r) == []

        assert Subscription.get_for_user(user).count() == 0

        Subscription.create(user, 'message', 'messenger')

        assert Subscription.get_for_user(user).count() == 1

    def test_get_for_message_cls(self):
        assert Subscription.get_for_message_cls('mymsg').count() == 0

        Subscription.create('aaa', 'mymsg', 'messenger')
        Subscription.create('bbb', 'mymsg', 'messenger2')

        assert Subscription.get_for_message_cls('mymsg').count() == 2

    def test_str(self):
        s = Subscription()
        s.address = 'aaa'

        assert 'aaa' in str(s)


class TestDispatchErrorModel(object):

    def test_str(self):
        e = DispatchError()
        e.dispatch_id = 444

        assert '444' in str(e)


class TestDispatchModel(object):

    def test_create(self, user):

        message = Message(cls='test_message')
        message.save()

        recipients_ = recipients('test_messenger', [user])
        recipients_ += recipients('buggy', 'idle')

        dispatches = Dispatch.create(message, recipients_)
        assert isinstance(dispatches[0], Dispatch)
        assert  isinstance(dispatches[1], Dispatch)
        assert dispatches[0].message_id == message.id
        assert dispatches[1].message_id == message.id
        assert dispatches[0].messenger == 'test_messenger'
        assert dispatches[1].messenger == 'buggy'

        dispatches = Dispatch.create(message, Recipient('msgr', None, 'address'))
        assert len(dispatches) == 1

    def test_log_dispatches_errors(self):

        assert DispatchError.objects.count() == 0

        m = Message()
        m.save()

        d1 = Dispatch(message_id=m.id)
        d1.save()

        d1.error_log = 'some_text'

        Dispatch.log_dispatches_errors([d1])
        errors = DispatchError.objects.all()
        assert len(errors) == 1
        assert errors[0].error_log == 'some_text'

    def test_get_unread(self):

        m = Message()
        m.save()

        d1 = Dispatch(message_id=m.id)
        d1.save()

        d2 = Dispatch(message_id=m.id)
        d2.save()
        assert Dispatch.get_unread().count() == 2

        d2.read_status = Dispatch.READ_STATUS_READ
        d2.save()
        assert Dispatch.get_unread().count() == 1

    def test_set_dispatches_statuses(self):

        m = Message()
        m.save()

        d = Dispatch(message_id=m.id)
        d.save()

        Dispatch.set_dispatches_statuses(**{'sent': [d]})
        d_ = Dispatch.objects.get(pk=d.id)
        assert d_.dispatch_status == Dispatch.DISPATCH_STATUS_SENT
        assert d_.retry_count == 1

        Dispatch.set_dispatches_statuses(**{'error': [d]})
        d_ = Dispatch.objects.get(pk=d.id)
        assert d_.dispatch_status == Dispatch.DISPATCH_STATUS_ERROR
        assert d_.retry_count == 2

    def test_str(self):
        d = Dispatch()
        d.address = 'tttt'

        assert 'tttt' in str(d)

    def test_mark_read(self):
        d = Dispatch()
        assert d.read_status == d.READ_STATUS_UNDREAD
        d.mark_read()
        assert d.read_status == d.READ_STATUS_READ


class TestMessageModel(object):

    def test_create(self, user):
        m, _ = Message.create('some', {'abc': 'abc'}, sender=user, priority=22)
        assert m.cls == 'some'
        assert m.context == {'abc': 'abc'}
        assert m.sender == user
        assert m.priority == 22
        assert not m.dispatches_ready

        ctx = {'a': 'a', 'b': 'b'}
        m, _ = Message.create('some2', ctx)
        assert m.cls == 'some2'
        assert m.context == ctx
        assert m.sender is None
        assert not m.dispatches_ready

    def test_deserialize_context(self):
        m = Message(cls='some_cls', context={'a': 'a', 'b': 'b', 'c': 'c'})
        m.save()

        m2 = Message.objects.get(pk=m.pk)
        assert m2.context == {'a': 'a', 'b': 'b', 'c': 'c'}

    def test_get_type(self):
        m = Message(cls='test_message')

        assert m.get_type() is MessageForTest

    def test_str(self):
        m = Message()
        m.cls = 'aaa'

        assert str(m) == 'aaa'
