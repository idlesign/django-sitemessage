from contextlib import contextmanager

from ..utils import Recipient, is_iterable, get_registered_message_type
from ..models import Dispatch
from ..exceptions import UnknownMessageTypeError, MessengerException


class MessengerBase(object):
    """Base class for messengers used by sitemessage.

    Custom messenger classes, implementing various message delivery
    mechanics, other messenger classes must inherit from this one.

    """

    # Messenger alias to address it from different places, Should rather be quite unique %)
    alias = None
    # Title to show to user.
    title = None

    # Makes subscription for this messenger messages available for users (see get_user_preferences_for_ui())
    allow_user_subscription = True

    address_attr = None
    """User object attribute containing address."""

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

    @contextmanager
    def before_after_send_handling(self):
        """Context manager that allows to execute send wrapped
        in before_send() and after_send().

        """
        self._init_delivery_statuses_dict()
        self.before_send()

        try:
            yield

        finally:
            self.after_send()
            self._update_dispatches()

    def send_test_message(self, to, text):
        """Sends a test message using messengers settings.

        :param str to: an address to send test message to
        :param str text: text to send
        """
        with self.before_after_send_handling():
            result = self._test_message(to, text)
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
        :rtype: str|object

        """
        address = recipient

        address_attr = cls.address_attr

        if address_attr:
            address = getattr(recipient, address_attr, None) or address

        return address

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
        with self.before_after_send_handling():
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
                        try:
                            if message_type_cache is None and not message_cls.has_dynamic_context:
                                # If a message class doesn't depend upon a dispatch data for message compilation,
                                # we'd compile a message just once.
                                message_type_cache = message_cls.compile(message_model, self, dispatch=dispatch)

                            dispatch.message_cache = message_type_cache or message_cls.compile(
                                message_model, self, dispatch=dispatch)

                        except Exception as e:
                            self.mark_error(dispatch, e, message_cls)

                self.send(message_cls, message_model, dispatch_models)

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


class RequestsMessengerBase(MessengerBase):
    """Shared requests-based messenger base class.

    Uses `requests` module: https://pypi.python.org/pypi/requests

    """
    timeout = 10
    """Request timeout."""

    def __init__(self, proxy=None, **kwargs):
        """Configures messenger.

        :param dict|Callable: Dictionary of proxy settings,
            or a callable returning such a dictionary.

        """
        import requests

        self.lib = requests
        self.proxy = proxy

    def _get_common_params(self):
        """Returns common parameters for every request."""

        proxy = self.proxy

        if proxy:

            if callable(proxy):
                proxy = proxy()

        params = {
            'timeout': self.timeout,
            'proxy': proxy or None
        }

        return params

    def get(self, url, json=True):
        """Performs POST and returns data.

        :param url:
        :param json: Expect json data and return it as dict.

        :rtype: str|dict

        """
        try:
            params = self._get_common_params()
            response = self.lib.get(url, **params)
            result = response.json() if json else response.text
            return result

        except self.lib.exceptions.RequestException as e:
            raise MessengerException(e)

    def post(self, url, data):
        """Performs POST and returns data.

        :param url:
        :param data: data to send.

        """
        try:
            params = self._get_common_params()
            response = self.lib.post(url, data=data, **params)
            result = response.json()
            return result

        except self.lib.exceptions.RequestException as e:
            raise MessengerException(e)

    def _test_message(self, to, text):
        return self._send_message(self._build_message(text, to=to))

    def _build_message(self, text, to=None):
        """Builds a message before send.

        :param text: Contents to add to message.
        :param to: Recipient address.

        :rtype: str

        """
        return text

    def _send_message(self, msg, to=None):
        """Should implement actual sending.

        :param msg: Contents to add to message.
        :param to: Recipient address.

        """
        raise NotImplementedError  # pragma: nocover

    def send(self, message_cls, message_model, dispatch_models):
        for dispatch_model in dispatch_models:
            try:
                msg = self._build_message(dispatch_model.message_cache, to=dispatch_model.address)
                self._send_message(msg)
                self.mark_sent(dispatch_model)

            except Exception as e:
                self.mark_error(dispatch_model, e, message_cls)
