from collections import namedtuple, defaultdict, OrderedDict
from threading import local

from django.utils import six

try:
    from django.utils.module_loading import import_module
except ImportError:
    # Django <=1.9.0
    from django.utils.importlib import import_module

from etc.toolbox import get_site_url as get_site_url_, import_app_module, import_project_modules

from .settings import APP_MODULE_NAME, SITE_URL
from .exceptions import UnknownMessageTypeError, UnknownMessengerError


_MESSENGERS_REGISTRY = OrderedDict()
_MESSAGES_REGISTRY = OrderedDict()

_MESSAGES_FOR_APPS = defaultdict(dict)

_THREAD_LOCAL = local()
_THREAD_SITE_URL = 'sitemessage_site_url'


def get_site_url():
    """Returns a URL for current site.

    :return:
    """

    site_url = getattr(_THREAD_LOCAL, _THREAD_SITE_URL, None)
    if site_url is None:
        site_url = SITE_URL or get_site_url_()
        setattr(_THREAD_LOCAL, _THREAD_SITE_URL, site_url)

    return site_url


def get_message_type_for_app(app_name, default_message_type_alias):
    """Returns a registered message type object for a given application.

    Supposed to be used by reusable applications authors,
    to get message type objects which may be overridden by project authors
    using `override_message_type_for_app`.

    :param str app_name:
    :param str default_message_type_alias:
    :return: a message type object overridden is so, or the default
    :rtype: MessageBase
    """
    message_type = default_message_type_alias
    try:
        message_type = _MESSAGES_FOR_APPS[app_name][message_type]
    except KeyError:
        pass
    return get_registered_message_type(message_type)


def override_message_type_for_app(app_name, app_message_type_alias, new_message_type_alias):
    """Overrides a given message type used by a certain application with another one.

    Intended for projects authors, who need to customize messaging behaviour
    of a certain thirdparty app (supporting this feature).
    To be used in conjunction with `get_message_type_for_app`.

    :param str app_name:
    :param str app_message_type_alias:
    :param str new_message_type_alias:
    :return:
    """
    global _MESSAGES_FOR_APPS

    _MESSAGES_FOR_APPS[app_name][app_message_type_alias] = new_message_type_alias


def register_messenger_objects(*messengers):
    """Registers (configures) messengers.

    :param list messengers: MessengerBase heirs instances.
    """
    global _MESSENGERS_REGISTRY

    for messenger in messengers:
        _MESSENGERS_REGISTRY[messenger.get_alias()] = messenger


def get_registered_messenger_objects():
    """Returns registered (configured) messengers dict
    indexed by messenger aliases.

    :return: dict
    :rtype: dict
    """
    return _MESSENGERS_REGISTRY


def get_registered_messenger_object(messenger):
    """Returns registered (configured) messenger by alias,

    :param str messenger: messenger alias
    :return: MessengerBase heirs instances.
    :rtype: MessengerBase
    """
    try:
        return _MESSENGERS_REGISTRY[messenger]
    except KeyError:
        raise UnknownMessengerError('`%s` messenger is not registered' % messenger)


def register_message_types(*message_types):
    """Registers message types (classes).

    :param list message_types: MessageBase heir classes.
    """
    global _MESSAGES_REGISTRY

    for message in message_types:
        _MESSAGES_REGISTRY[message.get_alias()] = message


def get_registered_message_types():
    """Returns registered message types dict indexed by their aliases.

    :return: dict
    :rtype: dict
    """
    return _MESSAGES_REGISTRY


def get_registered_message_type(message_type):
    """Returns registered message type (class) by alias,

    :param str message_type: message type alias
    :return: MessageBase heirs instances.
    :rtype: MessageBase
    """
    try:
        return _MESSAGES_REGISTRY[message_type]
    except KeyError:
        raise UnknownMessageTypeError('`%s` message class is not registered' % message_type)


def import_app_sitemessage_module(app):
    """Returns a submodule of a given app

    :param str app: application name
    :return: submodule or None
    :rtype: module or None
    """
    return import_app_module(app, APP_MODULE_NAME)


def import_project_sitemessage_modules():
    """Imports sitemessages modules from registered apps."""
    return import_project_modules(APP_MODULE_NAME)


def is_iterable(v):
    """Tells whether the thing is an iterable.
    NB: strings do not count even on Py3.

    """
    return hasattr(v, '__iter__') and not isinstance(v, six.string_types)


# Class used to represent message recipients.
Recipient = namedtuple('Recipient', ('messenger', 'user', 'address'))


def recipients(messenger, addresses):
    """Structures recipients data.

    :param str, MessageBase messenger: MessengerBase heir
    :param list addresses: recipients addresses or Django User model heir instances (NOTE: if supported by a messenger)
    :return: list of Recipient
    :rtype: list
    """
    if isinstance(messenger, six.string_types):
        messenger = get_registered_messenger_object(messenger)
    return messenger._structure_recipients_data(addresses)
