from collections import OrderedDict, defaultdict
from operator import itemgetter

from django import VERSION
from django.utils import six
from django.conf.urls import patterns, url

from .models import Message, Dispatch, Subscription
from .exceptions import UnknownMessengerError, UnknownMessageTypeError
from .messages.plain import PlainTextMessage
from .views import mark_read, unsubscribe

# NB: Some of these unused imports are exposed as part of toolbox API.
from .messages import register_builtin_message_types
from .utils import (
    is_iterable, import_project_sitemessage_modules, get_site_url, recipients,
    register_messenger_objects, get_registered_messenger_object, get_registered_messenger_objects,
    register_message_types, get_registered_message_type, get_registered_message_types,
    get_message_type_for_app, override_message_type_for_app,
)


_ALIAS_SEP = '|'
_PREF_POST_KEY = 'sm_user_pref'


if VERSION < (1, 7, 0):
    # Trying import sitemessage settings files from project apps.
    import_project_sitemessage_modules()


def schedule_messages(messages, recipients=None, sender=None, priority=None):
    """Schedules a message or messages.

    :param MessageBase|str|list messages: str or MessageBase heir or list - use str to create PlainTextMessage.
    :param list|None recipients: recipients addresses or Django User model heir instances
        If `None` Dispatches should be created before send using `prepare_dispatches()`.
    :param User|None sender: User model heir instance
    :param int priority: number describing message priority. If set overrides priority provided with message type.
    :return: list of tuples - (message_model, dispatches_models)
    :rtype: list
    """
    if not is_iterable(messages):
        messages = (messages,)

    results = []
    for message in messages:
        if isinstance(message, six.string_types):
            message = PlainTextMessage(message)

        resulting_priority = message.priority
        if priority is not None:
            resulting_priority = priority
        results.append(message.schedule(sender=sender, recipients=recipients, priority=resulting_priority))

    return results


def send_scheduled_messages(priority=None, ignore_unknown_messengers=False, ignore_unknown_message_types=False):
    """Sends scheduled messages.

    :param int, None priority: number to limit sending message by this priority.
    :param bool ignore_unknown_messengers: to silence UnknownMessengerError
    :param bool ignore_unknown_message_types: to silence UnknownMessageTypeError
    :raises UnknownMessengerError:
    :raises UnknownMessageTypeError:
    """
    dispatches_by_messengers = Dispatch.group_by_messengers(Dispatch.get_unsent(priority=priority))

    for messenger_id, messages in dispatches_by_messengers.items():
        try:
            messenger_obj = get_registered_messenger_object(messenger_id)
            messenger_obj._process_messages(messages, ignore_unknown_message_types=ignore_unknown_message_types)
        except UnknownMessengerError:
            if ignore_unknown_messengers:
                continue
            raise


def prepare_dispatches():
    """Automatically creates dispatches for messages without them.

    :return: list of Dispatch
    :rtype: list
    """
    dispatches = []
    target_messages = Message.get_without_dispatches()

    cache = {}

    for message_model in target_messages:

        if message_model.cls not in cache:
            message_cls = get_registered_message_type(message_model.cls)
            subscribers = message_cls.get_subscribers()
            cache[message_model.cls] = (message_cls, subscribers)
        else:
            message_cls, subscribers = cache[message_model.cls]

        dispatches.extend(message_cls.prepare_dispatches(message_model))

    return dispatches


def get_user_preferences_for_ui(user, message_filter=None, messenger_filter=None, new_messengers_titles=None):
    """Returns a two element tuple with user subscription preferences to render in UI.

    Message types with the same titles are merged into one row.

    First element:
        A list of messengers titles.

    Second element:
        User preferences dictionary indexed by message type titles.
        Preferences (dictionary values) are lists of tuples:
            (preference_alias, is_supported_by_messenger_flag, user_subscribed_flag)

        Example:
            {'My message type': [('test_message|smtp', True, False), ...]}

    :param User user:
    :param callable|None message_filter: A callable accepting a message object to filter out message types
    :param callable|None messenger_filter: A callable accepting a messenger object to filter out messengers
    :return:
    """
    if new_messengers_titles is None:
        new_messengers_titles = {}

    msgr_to_msg = defaultdict(set)
    msg_titles = OrderedDict()
    msgr_titles = OrderedDict()

    for msgr in get_registered_messenger_objects().values():
        if not (messenger_filter is None or messenger_filter(msgr)) or not msgr.allow_user_subscription:
            continue

        msgr_alias = msgr.alias
        msgr_title = new_messengers_titles.get(msgr.alias) or msgr.title

        for msg in get_registered_message_types().values():
            if not (message_filter is None or message_filter(msg)) or not msg.allow_user_subscription:
                continue

            msgr_supported = msg.supported_messengers
            is_supported = (not msgr_supported or msgr.alias in msgr_supported)

            if not is_supported:
                continue

            msg_alias = msg.alias
            msg_titles.setdefault('%s' % msg.title, []).append(msg_alias)

            msgr_to_msg[msgr_alias].update((msg_alias,))
            msgr_titles[msgr_title] = msgr_alias

    def sort_titles(titles):
        return OrderedDict(sorted([(k, v) for k, v in titles.items()], key=itemgetter(0)))

    msgr_titles = sort_titles(msgr_titles)

    user_prefs = OrderedDict()

    user_subscriptions = ['%s%s%s' % (pref.message_cls, _ALIAS_SEP, pref.messenger_cls)
                          for pref in Subscription.get_for_user(user)]

    for msg_title, msg_aliases in sort_titles(msg_titles).items():
        for __, msgr_alias in msgr_titles.items():
            msg_candidates = msgr_to_msg[msgr_alias].intersection(msg_aliases)

            alias = ''
            msg_supported = False
            subscribed = False

            if msg_candidates:
                alias = '%s%s%s' % (msg_candidates.pop(), _ALIAS_SEP, msgr_alias)
                msg_supported = True
                subscribed = alias in user_subscriptions

            user_prefs.setdefault(msg_title, []).append((alias, msg_supported, subscribed))

    return msgr_titles.keys(), user_prefs


def set_user_preferences_from_request(request):
    """Sets user subscription preferences using data from a request.

    Expects data sent by form built with `sitemessage_prefs_table` template tag.

    :param request:
    :rtype: bool
    :return: Flag, whether prefs were found in the request.
    """
    prefs = []
    for pref in request.POST.getlist(_PREF_POST_KEY):
        message_alias, messenger_alias = pref.split(_ALIAS_SEP)
        try:
            get_registered_message_type(message_alias)
            get_registered_messenger_object(messenger_alias)
        except (UnknownMessengerError, UnknownMessageTypeError):
            pass
        else:
            prefs.append((message_alias, messenger_alias))

    Subscription.replace_for_user(request.user, prefs)

    return bool(prefs)


def get_sitemessage_urls():
    """Returns sitemessage urlpatterns, that can be attached to urlpatterns of a project:

        # Example from urls.py.

        from sitemessage.toolbox import get_sitemessage_urls

        urlpatterns = patterns('',
            # Your URL Patterns belongs here.

        ) + get_sitemessage_urls()  # Now attaching additional URLs.

    """
    url_unsubscribe = url(
        r'^messages/unsubscribe/(?P<message_id>\d+)/(?P<dispatch_id>\d+)/(?P<hashed>[^/]+)/$',
        unsubscribe,
        name='sitemessage_unsubscribe'
    )

    url_mark_read = url(
        r'^messages/ping/(?P<message_id>\d+)/(?P<dispatch_id>\d+)/(?P<hashed>[^/]+)/$',
        mark_read,
        name='sitemessage_mark_read'
    )

    if VERSION >= (1, 9):
        return [url_unsubscribe, url_mark_read]

    return patterns('', url_unsubscribe, url_mark_read)
