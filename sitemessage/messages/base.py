from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils.crypto import salted_hmac
from django.utils.translation import ugettext as _
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils.six import string_types

from ..utils import Recipient, recipients, get_site_url, get_registered_messenger_object
from ..models import Message, Dispatch, Subscription
from ..signals import sig_unsubscribe_success, sig_unsubscribe_failed, sig_mark_read_success, sig_mark_read_failed
from ..exceptions import UnknownMessengerError


APP_URLS_ATTACHED = None


class MessageBase(object):
    """Base class for messages used by sitemessage.
    Customized message handling is available through inheritance.

    """

    # List of supported messengers (aliases).
    supported_messengers = []

    # Message type alias to address it from different places, Should rather be quite unique %)
    alias = None

    # Title to show to user.
    title = _('Notification')

    # Number describing message priority. Can be overridden by `priority` provided with schedule_messages().
    priority = None

    # This flag is used to optimize template compilation process.
    # If True template will be compiled for every dispatch (and dispatch data will be available in it)
    # instead of just once per message.
    has_dynamic_context = False

    # Template file extension. Considered when the below mentioned `template` field is not set.
    template_ext = 'tpl'

    # Path to the template to be used for message rendering.
    # If not set, will be deduced from message, messenger data (e.g. `sitemessage/plain_smtp.txt`)
    # and `template_ext` (see above).
    template = None

    # This limits the number of send attempts before message delivery considered failed.
    send_retry_limit = 10

    # Makes subscription for this message type available for users (see get_user_preferences_for_ui())
    allow_user_subscription = True

    _message_model = None
    _dispatch_models = None

    SIMPLE_TEXT_ID = 'stext_'

    def __init__(self, context=None, template_path=None):
        """Initializes a message.

        :param dict, str context: data to be used for message rendering (e.g. in templates)
        :param str template_path: template path
        """
        context_base = {
            'tpl': None,  # Template path to use
            'use_tpl': False  # Use template boolean flag
        }

        if context is not None:
            self.update_context(context_base, context, template_path=template_path)

        self.context = context_base

    @classmethod
    def get_alias(cls):
        """Returns message type alias.

        :return: str
        :rtype: str
        """
        if cls.alias is None:
            cls.alias = cls.__name__
        return cls.alias

    def __str__(self):
        return self.__class__.get_alias()

    def get_context(self):
        """Returns message context.

        :return: dict
        :rtype: dict
        """
        return self.context

    def schedule(self, recipients=None, sender=None, priority=None):
        """Schedules message for a delivery.
        Puts message (and dispatches if any) data into DB.

        :param list|None recipients: recipient (or a list) or None.
            If `None` Dispatches should be created before send using `prepare_dispatches()`.
        :param User|None sender: Django User model heir instance
        :param int|None priority: number describing message priority
        :return: a tuple with message model and a list of dispatch models.
        :rtype: tuple
        """
        if priority is None:
            priority = self.priority

        self._message_model, self._dispatch_models = Message.create(
            self.get_alias(), self.get_context(), recipients=recipients, sender=sender, priority=priority
        )
        return self._message_model, self._dispatch_models

    @classmethod
    def recipients(cls, messenger, addresses):
        """Shorcut method. See `recipients()`,"""
        return recipients(messenger, addresses)

    @classmethod
    def get_subscribers(cls):
        """Returns a list of Recipient objects subscribed for this message type.

        :return:
        """
        subscribers_raw = Subscription.get_for_message_cls(cls.alias)
        subscribers = []

        for subscriber in subscribers_raw:
            messenger_cls = subscriber.messenger_cls
            address = subscriber.address
            recipient = subscriber.recipient
            if address is None:
                try:
                    address = get_registered_messenger_object(messenger_cls).get_address(recipient)
                except UnknownMessengerError:
                    pass

            if address and isinstance(address, string_types):
                subscribers.append(Recipient(messenger_cls, recipient, address))

        return subscribers

    @classmethod
    def get_dispatch_hash(cls, dispatch_id, message_id):
        """Returns a hash string for validation purposes.

        :param int dispatch_id:
        :param int message_id:
        :return:
        """
        return salted_hmac('%s' % dispatch_id, '%s|%s' % (message_id, dispatch_id)).hexdigest()

    @classmethod
    def get_mark_read_directive(cls, message_model, dispatch_model):
        """Returns mark read directive (command, URL, etc.) string.

        :param Message message_model:
        :param Dispatch dispatch_model:
        :return:
        """
        return cls._get_url('sitemessage_mark_read', message_model, dispatch_model)

    @classmethod
    def get_unsubscribe_directive(cls, message_model, dispatch_model):
        """Returns an unsubscribe directive (command, URL, etc.) string.

        :param Message message_model:
        :param Dispatch dispatch_model:
        :return:
        """
        return cls._get_url('sitemessage_unsubscribe', message_model, dispatch_model)

    @classmethod
    def _get_url(cls, name, message_model, dispatch_model):
        """Returns a common pattern sitemessage URL.

        :param str name: URL name
        :param Message message_model:
        :param Dispatch|None dispatch_model:
        :return:
        """
        global APP_URLS_ATTACHED

        url = ''

        if dispatch_model is None:
            return url

        if APP_URLS_ATTACHED != False:  # sic!

            hashed = cls.get_dispatch_hash(dispatch_model.id, message_model.id)

            try:
                url = reverse(name, args=[message_model.id, dispatch_model.id, hashed])
                url = '%s%s' % (get_site_url(), url)
            except NoReverseMatch:
                if APP_URLS_ATTACHED is None:
                    APP_URLS_ATTACHED = False

        return url

    @classmethod
    def handle_unsubscribe_request(cls, request, message, dispatch, hash_is_valid, redirect_to):
        """Handles user subscription cancelling request.

        :param Request request: Request instance
        :param Message message: Message model instance
        :param Dispatch dispatch: Dispatch model instance
        :param bool hash_is_valid: Flag indicating that user supplied request signature is correct
        :param str redirect_to: Redirection URL
        :rtype: list
        """

        if hash_is_valid:
            Subscription.cancel(
                dispatch.recipient_id or dispatch.address, cls.alias, dispatch.messenger
            )
            signal = sig_unsubscribe_success
        else:
            signal = sig_unsubscribe_failed

        signal.send(cls, request=request, message=message, dispatch=dispatch)
        return redirect(redirect_to)

    @classmethod
    def handle_mark_read_request(cls, request, message, dispatch, hash_is_valid, redirect_to):
        """Handles a request to mark a message as read.

        :param Request request: Request instance
        :param Message message: Message model instance
        :param Dispatch dispatch: Dispatch model instance
        :param bool hash_is_valid: Flag indicating that user supplied request signature is correct
        :param str redirect_to: Redirection URL
        :rtype: list
        """

        if hash_is_valid:
            dispatch.mark_read()
            dispatch.save()
            signal = sig_mark_read_success
        else:
            signal = sig_mark_read_failed

        signal.send(cls, request=request, message=message, dispatch=dispatch)
        return redirect(redirect_to)

    @classmethod
    def get_template(cls, message, messenger):
        """Get a template path to compile a message.

        1. `tpl` field of message context;
        2. `template` field of message class;
        3. deduced from message, messenger data and `template_ext` message type field
           (e.g. `sitemessage/messages/plain__smtp.txt` for `plain` message type).

        :param Message message: Message model
        :param MessengerBase messenger: a MessengerBase heir
        :return: str
        :rtype: str
        """
        template = message.context.get('tpl', None)

        if template:  # Template name is taken from message context.
            return template

        if cls.template is None:
            cls.template = 'sitemessage/messages/%s__%s.%s' % (
                cls.get_alias(), messenger.get_alias(), cls.template_ext
            )
        return cls.template

    @classmethod
    def compile(cls, message, messenger, dispatch=None):
        """Compiles and returns a message text.

        Considers `use_tpl` field from message context to decide whether
        template compilation is used.

        Otherwise a SIMPLE_TEXT_ID field from message context is used as message contents.

        :param Message message: model instance
        :param MessengerBase messenger: MessengerBase heir instance
        :param Dispatch dispatch: model instance to consider context from
        :return: str
        :rtype: str
        """
        if message.context.get('use_tpl', False):
            context = message.context
            context.update({
                'SITE_URL': get_site_url(),
                'directive_unsubscribe': cls.get_unsubscribe_directive(message, dispatch),
                'directive_mark_read': cls.get_mark_read_directive(message, dispatch),
                'message_model': message,
                'dispatch_model': dispatch
            })
            context = cls.get_template_context(context)
            return render_to_string(cls.get_template(message, messenger), context)
        return message.context[cls.SIMPLE_TEXT_ID]

    @classmethod
    def get_template_context(cls, context):
        """Returns context dict for template compilation.

        This method might be reimplemented by a heir to add some data into
        context before template compilation.

        :param dict context: Initial context
        :return:
        """
        return context

    @classmethod
    def update_context(cls, base_context, str_or_dict, template_path=None):
        """Helper method to structure initial message context data.

        NOTE: updates `base_context` inplace.

        :param dict base_context: context dict to update
        :param dict, str str_or_dict: text representing a message, or a dict to be placed into message context.
        :param str template_path: template path to be used for message rendering
        """
        if isinstance(str_or_dict, dict):
            base_context.update(str_or_dict)
            base_context['use_tpl'] = True
        else:
            base_context[cls.SIMPLE_TEXT_ID] = str_or_dict

        if cls.SIMPLE_TEXT_ID in str_or_dict:
            base_context['use_tpl'] = False

        base_context['tpl'] = template_path

    @classmethod
    def prepare_dispatches(cls, message, recipients=None):
        """Creates Dispatch models for a given message and return them.

        :param Message message: Message model instance
        :param list|None recipients: A list or Recipient objects
        :return: list of created Dispatch models
        :rtype: list
        """
        return Dispatch.create(message, recipients or cls.get_subscribers())
