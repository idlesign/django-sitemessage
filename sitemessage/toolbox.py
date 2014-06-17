from django.utils import six

from .models import Message, Dispatch
from .utils import is_iterable, get_registered_messenger_object, get_registered_message_type, import_project_sitemessage_modules
from .exceptions import UnknownMessengerError
from .messages import PlainTextMessage


# Trying import sitemessage settings files from project apps.
import_project_sitemessage_modules()


def recipients(messenger, addresses):
    """Structures recipients data.

    :param messenger: MessengerBase heir
    :param addresses: list - recipients addresses or Django User model heir instances (NOTE: if supported by a messenger)
    :return: list of Recipient
    :rtype: list
    """
    if isinstance(messenger, six.string_types):
        messenger = get_registered_messenger_object(messenger)
    return messenger._structure_recipients_data(addresses)


def schedule_messages(messages, recipients=None, sender=None):
    """Sends a message(s).

    :param messages: str or MessageBase heir or list - use str to create PlainTextMessage.
    :param recipients: list - recipients addresses or Django User model heir instances
    :param sender: User - model heir instance
    :return: list of tuples - (message_model, dispatches_models)
    :rtype: list
    """
    if not is_iterable(messages):
        messages = (messages,)

    results = []
    for message in messages:
        if isinstance(message, six.string_types):
            message = PlainTextMessage(message)
        results.append(message.schedule(sender=sender, recipients=recipients))

    return results


def send_scheduled_messages(ignore_unknown_messengers=False, ignore_unknown_message_types=False):
    """Sends scheduled messages.

    :param ignore_unknown_messengers: bool - to silence UnknownMessengerError
    :param ignore_unknown_message_types: bool - to silence UnknownMessageTypeError
    :raises: UnknownMessengerError
    :raises: UnknownMessageTypeError
    """
    dispatches_by_messengers = Dispatch.group_by_messengers(Dispatch.get_unsent())

    for messenger_id, messages in dispatches_by_messengers.items():
        try:
            messenger_obj = get_registered_messenger_object(messenger_id)
            messenger_obj._process_messages(messages, ignore_unknown_message_types=ignore_unknown_message_types)
        except UnknownMessengerError:
            if ignore_unknown_messengers:
                continue
            raise


def prepare_dispatches():
    """Created dispatches for messages without them.

    It requires from a message type to implement `calculate_recipients()` method.

    :return: list of Dispatch
    :rtype: list
    """
    dispatches = []
    undispatched = Message.get_undispatched()
    for message_model in undispatched:
        message_cls = get_registered_message_type(message_model.cls)
        dispatches.extend(message_cls.prepare_dispatches(message_model))
    return dispatches