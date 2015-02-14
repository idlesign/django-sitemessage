from collections import namedtuple, defaultdict, OrderedDict
from threading import local

from django.core.urlresolvers import reverse, NoReverseMatch
from django.utils.crypto import salted_hmac
from django.utils import six
from django.utils.importlib import import_module
from django.utils.module_loading import module_has_submodule
from django.utils.translation import ugettext as _
from django.shortcuts import redirect
from django.template.loader import render_to_string
from etc.toolbox import get_site_url as get_site_url_

from .settings import APP_MODULE_NAME, SITE_URL
from .models import Message, Dispatch, Subscription
from .exceptions import UnknownMessageTypeError, UnknownMessengerError
from .signals import sig_unsubscribe_success, sig_unsubscribe_failed, sig_mark_read_success, sig_mark_read_failed


APP_URLS_ATTACHED = None

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
    module_name = APP_MODULE_NAME
    module = import_module(app)
    try:
        sub_module = import_module('%s.%s' % (app, module_name))
        return sub_module
    except:
        if module_has_submodule(module, module_name):
            raise
        return None


def import_project_sitemessage_modules():
    """Imports sitemessages modules from registered apps."""
    from django.conf import settings as django_settings
    submodules = []
    for app in django_settings.INSTALLED_APPS:
        module = import_app_sitemessage_module(app)
        if module is not None:
            submodules.append(module)
    return submodules


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


class MessengerBase(object):
    """Base class for messengers used by sitemessage.

    Custom messenger classes, implementing various message delivery
    mechanics, other messenger classes must inherit from this one.

    """

    # Messenger alias to address it from different places, Should rather be quite unique %)
    alias = None
    # Title to show to user.
    title = None

    # Dispatches by status dict will be here runtime. See init_delivery_statuses_dict().
    _st = None

    @classmethod
    def get_alias(cls):
        """Returns messenger alias.

        :return: str
        :rtype: str
        """
        if cls.alias is None:
            cls.alias = cls.__name__
        return cls.alias

    def __str__(self):
        return self.__class__.get_alias()

    def send_test_message(self, to, text):
        """Sends a test message using messengers settings.

        :param str to: an address to send test message to
        :param str text: text to send
        """
        self.before_send()
        result = self._test_message(to, text)
        self.after_send()
        return result

    def _test_message(self, to, text):
        """This method should be implemented by a heir to send a test message.
        
        :param str to: an address to send test message to
        :param str text: text to send
        """
        raise NotImplementedError(self.__class__.__name__ + ' must implement `test_message()`.')

    @classmethod
    def get_address(cls, recipient):
        """Returns recipient address.

        Heirs may override this to deduce address from `recipient` data
        (e.g. to get address from Django User model instance).

        :param object recipient: any object passed to `recipients()`
        :return: str
        :rtype: str
        """
        return recipient

    @classmethod
    def _structure_recipients_data(cls, recipients):
        """Converts recipients data into a list of Recipient objects.

        :param list recipients: list of objects
        :return: list of Recipient
        :rtype: list
        """
        try:  # That's all due Django 1.7 apps loading.
            from django.contrib.auth import get_user_model
            USER_MODEL = get_user_model()
        except ImportError:
            # Django 1.4 fallback.
            from django.contrib.auth.models import User as USER_MODEL

        if not is_iterable(recipients):
            recipients = (recipients,)

        objects = []
        for r in recipients:
            user = None
            if isinstance(r, USER_MODEL):
                user = r
            address = cls.get_address(r)  # todo maybe raise an exception of not a string?

            objects.append(Recipient(cls.get_alias(), user, address))

        return objects

    def _init_delivery_statuses_dict(self):
        """Initializes a dict indexed by message delivery statuses."""
        self._st = {
            'pending': [],
            'sent': [],
            'error': [],
            'failed': []
        }

    def mark_pending(self, dispatch):
        """Marks a dispatch as pending.

        Should be used within send().

        :param Dispatch dispatch: a Dispatch
        """
        self._st['pending'].append(dispatch)

    def mark_sent(self, dispatch):
        """Marks a dispatch as successfully sent.

        Should be used within send().

        :param Dispatch dispatch: a Dispatch
        """
        self._st['sent'].append(dispatch)

    def mark_error(self, dispatch, error_log, message_cls):
        """Marks a dispatch as having error or consequently as failed
        if send retry limit for that message type is exhausted.

        Should be used within send().

        :param Dispatch dispatch: a Dispatch
        :param str error_log: error message
        :param MessageBase message_cls: MessageBase heir
        """
        if message_cls.send_retry_limit is not None and (dispatch.retry_count + 1) >= message_cls.send_retry_limit:
            self.mark_failed(dispatch, error_log)
        else:
            dispatch.error_log = error_log
            self._st['error'].append(dispatch)

    def mark_failed(self, dispatch, error_log):
        """Marks a dispatch as failed.

        Sitemessage won't try to deliver already failed messages.

        Should be used within send().

        :param Dispatch dispatch: a Dispatch
        :param str error_log: str - error message
        """
        dispatch.error_log = error_log
        self._st['failed'].append(dispatch)

    def before_send(self):
        """This one is called right before send procedure.
        Usually heir will implement some messenger warm up (connect) code.

        """

    def after_send(self):
        """This one is called right after send procedure.
        Usually heir will implement some messenger cool down (disconnect) code.

        """

    def _process_messages(self, messages, ignore_unknown_message_types=False):
        """Performs message processing.

        :param dict messages: indexed by message id dict with messages data
        :param bool ignore_unknown_message_types: whether to silence exceptions
        :raises UnknownMessageTypeError:
        """
        self._init_delivery_statuses_dict()
        self.before_send()

        for message_id, message_data in messages.items():
            message_model, dispatch_models = message_data
            try:
                message_cls = get_registered_message_type(message_model.cls)
            except UnknownMessageTypeError:
                if ignore_unknown_message_types:
                    continue
                raise

            message_type_cache = None
            for dispatch in dispatch_models:
                if not dispatch.message_cache:  # Create actual message text for further usage.

                    if message_type_cache is None and not message_cls.has_dynamic_context:
                        # If a message class doesn't depend upon a dispatch data for message compilation,
                        # we'd compile a message just once.
                        message_type_cache = message_cls.compile(message_model, self, dispatch=dispatch)

                    dispatch.message_cache = message_type_cache or message_cls.compile(
                        message_model, self, dispatch=dispatch
                    )

            self.send(message_cls, message_model, dispatch_models)

        self.after_send()
        self._update_dispatches()

    def _update_dispatches(self):
        """Updates dispatched data in DB according to information gather by `mark_*` methods,"""
        Dispatch.log_dispatches_errors(self._st['error'] + self._st['failed'])
        Dispatch.set_dispatches_statuses(**self._st)
        self._init_delivery_statuses_dict()

    def send(self, message_cls, message_model, dispatch_models):
        """Main send method must be implement by all heirs.

        :param MessageBase message_cls: a MessageBase heir
        :param Message message_model: message model
        :param list dispatch_models: Dispatch models for this Message
        """
        raise NotImplementedError(self.__class__.__name__ + ' must implement `send()`.')


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
            subscribers.append(Recipient(subscriber.messenger_cls, subscriber.recipient, subscriber.address))

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
