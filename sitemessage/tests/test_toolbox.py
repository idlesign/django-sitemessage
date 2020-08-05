import pytest

try:
    from django.template.base import TemplateDoesNotExist, Template, TemplateSyntaxError
except ImportError:
    # Django 1.9+
    from django.template import TemplateDoesNotExist, Template, TemplateSyntaxError

from sitemessage.exceptions import UnknownMessengerError, SiteMessageConfigurationError
from sitemessage.models import Message, Dispatch, Subscription
from sitemessage.toolbox import send_scheduled_messages, get_user_preferences_for_ui, \
    set_user_preferences_from_request, _ALIAS_SEP, _PREF_POST_KEY


def test_get_user_preferences_for_ui(template_render_tag, template_context, user):
    messengers_titles, prefs = get_user_preferences_for_ui(user)

    assert len(prefs.keys()) == 3
    assert len(messengers_titles) == 8

    from .testapp.sitemessages import MessageForTest, MessengerForTest

    Subscription.create(user, MessageForTest, MessengerForTest)

    user_prefs = get_user_preferences_for_ui(
        user,
        message_filter=lambda m: m.alias == 'test_message',
        messenger_filter=lambda m: m.alias in ['smtp', 'test_messenger']
    )
    messengers_titles, prefs = user_prefs

    assert len(prefs.keys()) == 1
    assert len(messengers_titles) == 2
    assert 'E-mail' in messengers_titles
    assert 'Test messenger' in messengers_titles

    html = template_render_tag(
        'sitemessage',
        'sitemessage_prefs_table from user_prefs',
        template_context({'user_prefs': user_prefs})
    )

    assert 'class="sitemessage_prefs' in html
    assert 'E-mail</th>' in html
    assert 'Test messenger</th>' in html
    assert 'value="test_message|smtp"' in html
    assert 'value="test_message|test_messenger" checked' in html

    prefs_row = prefs.popitem()
    assert prefs_row[0] == 'Test message type'
    assert ('test_message|smtp', True, False) in prefs_row[1]
    assert ('test_message|test_messenger', True, True) in prefs_row[1]


def test_templatetag_fails_silent(template_render_tag, template_context):
    html = template_render_tag(
        'sitemessage',
        'sitemessage_prefs_table from user_prefs',
        template_context({'user_prefs': 'a'})
    )

    assert html == ''


def test_templatetag_fails_loud(template_render_tag, template_context, settings):

    settings.DEBUG = True

    with pytest.raises(SiteMessageConfigurationError):
        template_render_tag(
            'sitemessage', 'sitemessage_prefs_table from user_prefs',
            template_context({'user_prefs': 'a'}))

    with pytest.raises(TemplateSyntaxError):
        template_render_tag('sitemessage', 'sitemessage_prefs_table user_prefs')


def test_send_scheduled_messages_unknown_messenger():
    message = Message()
    message.save()
    dispatch = Dispatch(message=message, messenger='unknownname')
    dispatch.save()

    with pytest.raises(UnknownMessengerError):
        send_scheduled_messages()

    send_scheduled_messages(ignore_unknown_messengers=True)


def test_set_user_preferences_from_request(request_post, user):
    set_user_preferences_from_request(
        request_post('/', data={_PREF_POST_KEY: f'aaa{_ALIAS_SEP}qqq'}, user=user))

    subs = Subscription.objects.all()
    assert len(subs) == 0

    set_user_preferences_from_request(
        request_post('/', data={_PREF_POST_KEY: f'test_message{_ALIAS_SEP}test_messenger'}, user=user))

    subs = Subscription.objects.all()
    assert len(subs) == 1
