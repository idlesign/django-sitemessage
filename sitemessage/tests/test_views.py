import pytest

try:
    from django.urls import reverse

except ImportError:  # Django<2.0
    from django.core.urlresolvers import reverse


from sitemessage.models import Dispatch

from sitemessage.models import Subscription
from sitemessage.toolbox import schedule_messages, recipients
from sitemessage.signals import (
    sig_unsubscribe_success,
    sig_unsubscribe_failed,
    sig_mark_read_success,
    sig_mark_read_failed,
)

from .testapp.sitemessages import MessagePlainForTest, MessengerForTest


class TestViews:

    STATUS_SUCCESS = 'success'
    STATUS_FAIL = 'fail'

    @pytest.fixture
    def setup(self, user, request_client):

        def catcher_success(*args, **kwargs):
            self.status = self.STATUS_SUCCESS
        self.catcher_success = catcher_success

        def catcher_fail(*args, **kwargs):
            self.status = self.STATUS_FAIL
        self.catcher_fail = catcher_fail

        self.user = user
        self.request_client = request_client()

        msg_type = MessagePlainForTest('sometext')
        self.msg_type = msg_type

        msg_model, _ = schedule_messages(msg_type, recipients(MessengerForTest, user))[0]
        dispatch = Dispatch.objects.all()[0]
        self.msg_model = msg_model
        self.dispatch = dispatch

        dispatch_hash = msg_type.get_dispatch_hash(dispatch.id, msg_model.id)
        self.dispatch_hash = dispatch_hash

    def send_request(self, msg_id, dispatch_id, dispatch_hash, expected_status):
        self.request_client.get(reverse(self.view_name, args=[msg_id, dispatch_id, dispatch_hash]))
        assert self.status == expected_status
        self.status = None

    def generic_view_test(self):
        # Unknown dispatch ID.
        self.send_request(self.msg_model.id, 999999, self.dispatch_hash, self.STATUS_FAIL)
        # Invalid hash.
        self.send_request(self.msg_model.id, self.dispatch.id, 'nothash', self.STATUS_FAIL)
        # Message ID mismatch.
        self.send_request(999999, self.dispatch.id, self.dispatch_hash, self.STATUS_FAIL)

    def test_unsubscribe(self, setup):
        self.view_name = 'sitemessage_unsubscribe'

        sig_unsubscribe_success.connect(self.catcher_success, weak=False)
        sig_unsubscribe_failed.connect(self.catcher_fail, weak=False)

        self.generic_view_test()

        subscr = Subscription(
            message_cls=self.msg_type, messenger_cls=MessengerForTest.alias, recipient=self.user
        )
        subscr.save()
        assert len(Subscription.objects.all()) == 1

        self.send_request(self.msg_model.id, self.dispatch.id, self.dispatch_hash, self.STATUS_SUCCESS)
        assert len(Subscription.objects.all()) == 0

    def test_mark_read(self, setup):

        self.view_name = 'sitemessage_mark_read'

        sig_mark_read_success.connect(self.catcher_success, weak=False)
        sig_mark_read_failed.connect(self.catcher_fail, weak=False)

        self.generic_view_test()
        assert not Dispatch.objects.get(pk=self.dispatch.pk).is_read()

        self.send_request(self.msg_model.id, self.dispatch.id, self.dispatch_hash, self.STATUS_SUCCESS)
        assert Dispatch.objects.get(pk=self.dispatch.pk).is_read()
