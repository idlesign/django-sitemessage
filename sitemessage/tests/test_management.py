#! -*- encoding: utf-8 -*-
from __future__ import unicode_literals
from datetime import timedelta
from django.utils import timezone

from sitemessage.models import Message, Dispatch
from sitemessage.toolbox import recipients


def test_sitemessage_cleanup(capsys, command_run, user_create):

    def create_message(dispatches_count):

        message = Message(cls='test_message')
        message.save()

        users = []

        for _ in range(dispatches_count):
            users.append(user_create())

        Dispatch.create(message, recipients('test_messenger', users))

        dispatches = Dispatch.objects.filter(dispatch_status=Dispatch.DISPATCH_STATUS_PENDING)

        for dispatch in dispatches:
            dispatch.dispatch_status = dispatch.DISPATCH_STATUS_SENT
            dispatch.save()

        return message, dispatches

    def get_all():
        return list(Message.objects.all()), list(Dispatch.objects.all())

    def assert_len(msg, dsp):
        msg_, dsp_ = get_all()
        assert len(msg_) == msg
        assert len(dsp_) == dsp

    msg1, dsp1 = create_message(dispatches_count=2)
    dsp1[0].time_dispatched = timezone.now() - timedelta(days=3)
    dsp1[0].save()

    msg2, dsp2 = create_message(dispatches_count=1)
    dsp2[0].time_dispatched = timezone.now() - timedelta(days=2)
    dsp2[0].save()

    msg3, dsp3 = create_message(dispatches_count=3)
    assert_len(3, 6)

    command_run('sitemessage_cleanup', options={'ago': '4'})
    assert_len(3, 6)

    command_run('sitemessage_cleanup', options={'ago': '2'})
    assert_len(2, 4)

    command_run('sitemessage_cleanup')

    assert_len(0, 0)

    out, err = capsys.readouterr()

    assert 'Cleaning up dispatches and messages' in out
    assert err == ''
