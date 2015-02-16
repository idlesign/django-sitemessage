import json

from django.core import exceptions
from django.db import models
from django.utils import timezone
from django.utils.six import with_metaclass, string_types
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import python_2_unicode_compatible
from django.conf import settings


USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


# This allows South to handle our custom 'CharFieldNullable' field.
if 'south' in settings.INSTALLED_APPS:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ['^sitemessage\.models\.ContextField'])


class ContextField(with_metaclass(models.SubfieldBase, models.TextField)):

    def to_python(self, value):
        if not value:
            return {}

        if isinstance(value, dict):
            return value

        try:
            return json.loads(value)
        except ValueError:
            raise exceptions.ValidationError(_('Value `%r` is not a valid context.') % value,
                                             code='invalid_context', params={'value': value},)

    def get_prep_value(self, value):
        return json.dumps(value)


@python_2_unicode_compatible
class Message(models.Model):

    time_created = models.DateTimeField(_('Time created'), auto_now_add=True, editable=False)
    sender = models.ForeignKey(USER_MODEL, verbose_name=_('Sender'), null=True, blank=True)
    cls = models.CharField(_('Message class'), max_length=250, db_index=True,
                           help_text=_('Message logic class identifier.'))
    context = ContextField(_('Message context'))
    priority = models.PositiveIntegerField(_('Priority'), default=0, db_index=True,
                                           help_text=_('Number describing message sending priority. Messages with '
                                                       'different priorities can be sent with different periodicity.'))
    dispatches_ready = models.BooleanField(_('Dispatches ready'), db_index=True, default=False,
                                           help_text=_('Indicates whether dispatches for this message are already '
                                                       'formed and ready to delivery.'))

    class Meta:
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')

    def __str__(self):
        return self.cls

    def get_type(self):
        """Returns message type (class) associated with the message.

        :raises UnknownMessageTypeError:
        """
        from .toolbox import get_registered_message_type
        return get_registered_message_type(self.cls)

    @classmethod
    def get_without_dispatches(cls):
        """Returns messages with no dispatches created.

        :return:
        """
        return cls.objects.filter(dispatches_ready=False).all()

    @classmethod
    def create(cls, message_class, context, recipients=None, sender=None, priority=None):
        """Creates a message (and dispatches).

        Returns a tuple: (message_model, list_of_dispatches)

        :param str message_class: alias of MessageBase heir
        :param dict context: context for a message
        :param list|None recipients: recipient (or a list) or None.
            If `None` Dispatches should be created before send using `prepare_dispatches()`.
        :param User|None sender: Django User model heir instance
        :param int|None priority: number describing message priority
        :return: a tuple with message model and a list of dispatch models.
        :rtype: tuple
        """
        dispatches_ready = False
        if recipients is not None:
            dispatches_ready = True

        msg_kwargs = {
            'cls': message_class,
            'context': context,
            'sender': sender,
            'dispatches_ready': dispatches_ready
        }

        if priority is not None:
            msg_kwargs['priority'] = priority

        message_model = cls(**msg_kwargs)
        message_model.save()
        dispatch_models = Dispatch.create(message_model, recipients)
        return message_model, dispatch_models


@python_2_unicode_compatible
class Dispatch(models.Model):

    DISPATCH_STATUS_PENDING = 1
    DISPATCH_STATUS_SENT = 2
    DISPATCH_STATUS_ERROR = 3
    DISPATCH_STATUS_FAILED = 4

    DISPATCH_STATUSES = (
        (DISPATCH_STATUS_PENDING, _('Pending')),
        (DISPATCH_STATUS_SENT, _('Sent')),
        (DISPATCH_STATUS_ERROR, _('Error')),
        (DISPATCH_STATUS_FAILED, _('Failed')),
    )

    READ_STATUS_UNDREAD = 0
    READ_STATUS_READ = 1

    READ_STATUSES = (
        (READ_STATUS_UNDREAD, _('Unread')),
        (READ_STATUS_READ, _('Read')),
    )

    error_log = None

    time_created = models.DateTimeField(_('Time created'), auto_now_add=True, editable=False)
    time_dispatched = models.DateTimeField(_('Time dispatched'), editable=False, null=True, blank=True,
                                           help_text=_('Time of the last delivery attempt.'))

    message = models.ForeignKey(Message, verbose_name=_('Message'))
    messenger = models.CharField(_('Messenger'), max_length=250, db_index=True,
                                 help_text=_('Messenger class identifier.'))

    recipient = models.ForeignKey(USER_MODEL, verbose_name=_('Recipient'), null=True, blank=True)
    address = models.CharField(_('Address'), max_length=250, help_text=_('Recipient address.'))
    retry_count = models.PositiveIntegerField(_('Retry count'), default=0,
                                              help_text=_('A number of delivery retries has already been made.'))

    message_cache = models.TextField(_('Message cache'), null=True, editable=False)
    dispatch_status = models.PositiveIntegerField(_('Dispatch status'), choices=DISPATCH_STATUSES,
                                                  default=DISPATCH_STATUS_PENDING)

    read_status = models.PositiveIntegerField(_('Read status'), choices=READ_STATUSES, default=READ_STATUS_UNDREAD)

    class Meta:
        verbose_name = _('Dispatch')
        verbose_name_plural = _('Dispatches')

    def __str__(self):
        return '%s [%s]' % (self.address, self.messenger)

    def is_read(self):
        """Returns message read flag.

        :rtype: bool
        :return:
        """
        return self.read_status == self.READ_STATUS_READ

    def mark_read(self):
        """Marks message as read (doesn't save it).

        :return:
        """
        self.read_status = self.READ_STATUS_READ

    @classmethod
    def log_dispatches_errors(cls, dispatches):
        """Batch logs dispatches delivery errors into DB.

        :param list dispatches:
        :return:
        """
        error_entries = []
        for dispatch in dispatches:
            # Saving message body cache for further usage.
            dispatch.save()
            error_entries.append(DispatchError(dispatch=dispatch, error_log=dispatch.error_log))
        DispatchError.objects.bulk_create(error_entries)

    @classmethod
    def set_dispatches_statuses(cls, **statuses):
        """Batch set dispatches delivery statuses using a [kwargs] dictionary
        of dispatch lists indexed by statuses.

        :param statuses:
        :return:
        """
        kwarg_status_map = {
            'sent': cls.DISPATCH_STATUS_SENT,
            'error': cls.DISPATCH_STATUS_ERROR,
            'failed': cls.DISPATCH_STATUS_FAILED,
            'pending': cls.DISPATCH_STATUS_PENDING,
        }
        for status_name, real_status in kwarg_status_map.items():
            if statuses.get(status_name, False):
                update_kwargs = {
                    'time_dispatched': timezone.now(),
                    'dispatch_status': real_status,
                    'retry_count': models.F('retry_count') + 1
                }
                cls.objects.filter(id__in=[d.id for d in statuses[status_name]]).update(**update_kwargs)

    @staticmethod
    def group_by_messengers(dispatches):
        """Groups dispatches by messages.

        :param list dispatches:
        :return:
        """
        by_messengers = {}
        for dispatch in dispatches:
            if dispatch.messenger not in by_messengers:
                by_messengers[dispatch.messenger] = {}

            if dispatch.message.id not in by_messengers[dispatch.messenger]:
                by_messengers[dispatch.messenger][dispatch.message.id] = (dispatch.message, [])

            by_messengers[dispatch.messenger][dispatch.message.id][1].append(dispatch)
        return by_messengers

    @classmethod
    def get_unsent(cls, priority=None):
        """Returns dispatches unsent (scheduled or with errors).

        :param int priority: Message priority filter
        :return:
        """
        filter_kwargs = {
            'dispatch_status__in': (cls.DISPATCH_STATUS_PENDING, cls.DISPATCH_STATUS_ERROR)
        }
        if priority is not None:
            filter_kwargs['message__priority'] = priority
        return cls.objects.select_related('message').filter(**filter_kwargs).order_by('-message__time_created').all()

    @classmethod
    def get_unread(cls):
        """Returns unread dispatches.

        :return:
        """
        return cls.objects.filter(read_status=cls.READ_STATUS_UNDREAD).select_related('message').all()

    @classmethod
    def create(cls, message_model, recipients):
        """Creates dispatches for given recipients.

        NB: dispatch models are bulk created and do not have IDs.

        :param Message message_model:
        :param recipients:
        :return:
        """
        objects = []
        if recipients:
            if not isinstance(recipients, (list, set)):
                recipients = (recipients,)

            for r in recipients:
                objects.append(cls(message=message_model, messenger=r.messenger, recipient=r.user, address=r.address))

            if objects:
                cls.objects.bulk_create(objects)

            if not message_model.dispatches_ready:
                message_model.dispatches_ready = True
                message_model.save()

        return objects


@python_2_unicode_compatible
class DispatchError(models.Model):

    time_created = models.DateTimeField(_('Time created'), auto_now_add=True, editable=False)
    dispatch = models.ForeignKey(Dispatch, verbose_name=_('Dispatch'))
    error_log = models.TextField(_('Text'))

    class Meta:
        verbose_name = _('Dispatch error')
        verbose_name_plural = _('Dispatch errors')

    def __str__(self):
        return 'Dispatch ID %s error entry' % self.dispatch_id


@python_2_unicode_compatible
class Subscription(models.Model):

    time_created = models.DateTimeField(_('Time created'), auto_now_add=True, editable=False)
    message_cls = models.CharField(_('Message class'), max_length=250, db_index=True,
                                   help_text=_('Message logic class identifier.'))
    messenger_cls = models.CharField(_('Messenger'), max_length=250, db_index=True,
                                     help_text=_('Messenger class identifier.'))
    recipient = models.ForeignKey(USER_MODEL, verbose_name=_('Recipient'), null=True, blank=True)
    address = models.CharField(_('Address'), max_length=250, null=True, help_text=_('Recipient address.'))

    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')

    def __str__(self):
        recipient = self.recipient_id or self.address
        return '%s [%s - %s]' % (recipient, self.message_cls, self.messenger_cls)

    @classmethod
    def get_for_user(cls, user):
        """Returns subscriptions for a given user.

        :param User user:
        :return:
        """
        if user.id is None:
            return []

        return cls.objects.filter(recipient=user)

    @classmethod
    def replace_for_user(cls, user, prefs):
        """Set subscription preferences for a given user.

        :param User user:
        :param list prefs: List of tuples (message_cls, messenger_cls)
        :return:
        """
        uid = user.id
        if uid is None:
            return False

        # Remove previous prefs.
        cls.objects.filter(recipient_id=uid).delete()

        new_prefs = []

        for pref in prefs:
            new_prefs.append(
                cls(**cls._get_base_kwargs(uid, pref[0], pref[1]))
            )

        if new_prefs:
            cls.objects.bulk_create(new_prefs)

        return True

    @classmethod
    def get_for_message_cls(cls, message_cls):
        """Returns subscriptions for a given message class alias.

        :param str message_cls:
        :return:
        """
        return cls.objects.select_related('recipient').filter(message_cls=message_cls)

    @classmethod
    def _get_base_kwargs(cls, recipient, message_cls, messenger_cls):

        if not isinstance(message_cls, string_types):
            message_cls = message_cls.alias

        if not isinstance(messenger_cls, string_types):
            messenger_cls = messenger_cls.alias

        base_kwargs = {
            'message_cls': message_cls,
            'messenger_cls': messenger_cls,
        }
        if isinstance(recipient, string_types):
            base_kwargs['address'] = recipient
        else:
            if not isinstance(recipient, int):
                recipient = recipient.id
            base_kwargs['recipient_id'] = recipient

        return base_kwargs

    @classmethod
    def create(cls, uid_or_address, message_cls, messenger_cls):
        """Creates a subscription for a recipient.

        :param int|str uid_or_address: User ID or address string.
        :param str|MessageBase message_cls: Message type alias or class
        :param str|MessengerBase messenger_cls: Messenger type alias or class
        :return:
        """
        obj = cls(**cls._get_base_kwargs(uid_or_address, message_cls, messenger_cls))
        obj.save()
        return obj

    @classmethod
    def cancel(cls, uid_or_address, message_cls, messenger_cls):
        """Cancels a subscription for a recipient.

        :param int|str uid_or_address: User ID or address string.
        :param str|MessageBase message_cls: Message type alias or class
        :param str|MessengerBase messenger_cls: Messenger type alias or class
        :return:
        """
        cls.objects.filter(
            **cls._get_base_kwargs(uid_or_address, message_cls, messenger_cls)
        ).delete()
