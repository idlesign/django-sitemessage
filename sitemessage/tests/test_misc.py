import pytest

from sitemessage.messages.base import MessageBase
from sitemessage.models import Message, Dispatch
from sitemessage.shortcuts import (
    schedule_email,
    schedule_jabber_message,
    schedule_tweet,
    schedule_facebook_message,
    schedule_telegram_message,
    schedule_vkontakte_message,
)

try:
    from django.template.base import TemplateDoesNotExist, Template, TemplateSyntaxError
except ImportError:
    # Django 1.9+
    from django.template import TemplateDoesNotExist, Template, TemplateSyntaxError

from django.core.mail import send_mail

from .testapp.sitemessages import MessagePlainForTest, MessageForTest, \
    MessengerForTest


class TestMessageSuite:

    def test_alias(self):
        message = type('MyMessage', (MessageBase,), {'alias': 'myalias'})  # type: MessageBase
        assert message.get_alias() == 'myalias'

        message = type('MyMessage', (MessageBase,), {})
        assert message.get_alias() == 'MyMessage'

        message = message()
        assert str(message) == 'MyMessage'

    def test_context(self):
        msg = MessageForTest({'title': 'My message!', 'name': 'idle'})
        assert msg.context == {'name': 'idle', 'title': 'My message!', 'tpl': None, 'use_tpl': True}

    def test_get_template(self):
        assert (
                MessageForTest.get_template(MessageForTest(), MessengerForTest('a', 'b')) ==
            'sitemessage/messages/test_message__test_messenger.html'
        )

    def test_compile_string(self):
        msg = MessagePlainForTest('simple')
        assert MessagePlainForTest.compile(msg, MessengerForTest('a', 'b')) == 'simple'

    def test_compile_dict(self):
        msg = MessageForTest({'title': 'My message!', 'name': 'idle'})
        with pytest.raises(TemplateDoesNotExist):
            MessageForTest.compile(msg, MessengerForTest('a', 'b'))

    def test_schedule(self, user):
        msg = MessagePlainForTest('schedule1')
        model, _ = msg.schedule()

        assert model.cls == msg.get_alias()
        assert model.context == msg.get_context()
        assert model.sender is None

        msg = MessagePlainForTest('schedule2')
        model, _ = msg.schedule(sender=user)
        assert model.sender == user


class TestCommands:

    def test_send_scheduled(self, command_run):
        command_run('sitemessage_send_scheduled', options=dict(priority=1))


class TestBackends:

    def test_email_backend(self, settings):
        settings.EMAIL_BACKEND = 'sitemessage.backends.EmailBackend'

        send_mail('subj', 'message', 'from@example.com', ['to@example.com'], fail_silently=False)
        dispatches = list(Dispatch.objects.all())
        assert len(dispatches) == 1
        assert dispatches[0].messenger == 'smtp'
        assert dispatches[0].address == 'to@example.com'
        assert dispatches[0].dispatch_status == Dispatch.DISPATCH_STATUS_PENDING
        assert dispatches[0].message.cls == 'email_html'
        assert dispatches[0].message.context['subject'] == 'subj'
        assert dispatches[0].message.context['contents'] == 'message'


class TestShortcuts:

    def test_schedule_email(self):
        schedule_email('some text', 'some@one.here')

        assert Message.objects.all()[0].cls == 'email_plain'
        assert Message.objects.count() == 1
        assert Dispatch.objects.count() == 1

        schedule_email({'header': 'one', 'body': 'two'}, 'some@one.here')

        assert Message.objects.all()[1].cls == 'email_html'
        assert Message.objects.count() == 2
        assert Dispatch.objects.count() == 2

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
