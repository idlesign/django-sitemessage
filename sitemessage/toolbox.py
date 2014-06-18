from django.utils import six

from .models import Message, Dispatch
from .utils import is_iterable, get_registered_messenger_object, get_registered_message_type, import_project_sitemessage_modules
from .exceptions import UnknownMessengerError
from .messages import PlainTextMessage


# Trying import sitemessage settings files from project apps.
import_project_sitemessage_modules()


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


def schedule_messages(messages, recipients=None, sender=None, priority=None):
    """Sends a message(s).

    :param MessageBase, str, list messages: str or MessageBase heir or list - use str to create PlainTextMessage.
    :param list recipients: recipients addresses or Django User model heir instances
    :param User sender: User model heir instance
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
