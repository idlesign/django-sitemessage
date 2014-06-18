import json

from datetime import datetime

from django.core import exceptions
from django.db import models
from django.utils.six import with_metaclass
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
            raise exceptions.ValidationError(_('Value `%r` is not a valid context.') % value, code='invalid_context', params={'value': value},)

    def get_prep_value(self, value):
        return json.dumps(value)


@python_2_unicode_compatible
class Message(models.Model):

    time_created = models.DateTimeField(_('Time created'), auto_now_add=True, editable=False)
    sender = models.ForeignKey(USER_MODEL, verbose_name=_('Sender'), null=True, blank=True)
    cls = models.CharField(_('Message class'), max_length=250, help_text=_('Message logic class identifier.'), db_index=True)
    context = ContextField(_('Message context'))
    priority = models.PositiveIntegerField(_('Priority'), help_text=_('Number describing message sending priority. Messages with different priorities can be sent with different periodicity.'), default=0, db_index=True)
    dispatches_ready = models.BooleanField(_('Dispatches ready'), db_index=True, default=False, help_text=_('Indicates whether dispatches for this message are already formed and ready to delivery.'))

    @classmethod
    def get_undispatched(cls):
        return cls.objects.filter(dispatches_ready=False).all()

    @classmethod
    def create(cls, message_class, context, recipients=None, sender=None, priority=None):
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

    class Meta:
        verbose_name = _('Message')
        verbose_name_plural = _('Messages')

    def __str__(self):
        return self.cls


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
    time_dispatched = models.DateTimeField(_('Time dispatched'), help_text=_('Time of the last delivery attempt.'), editable=False, null=True, blank=True)
    message = models.ForeignKey(Message, verbose_name=_('Message'))
    messenger = models.CharField(_('Messenger'), max_length=250, help_text=_('Messenger class identifier.'), db_index=True)
    recipient = models.ForeignKey(USER_MODEL, verbose_name=_('Recipient'), null=True, blank=True)
    address = models.CharField(_('Address'), max_length=250, help_text=_('Recipient address.'))
    retry_count = models.PositiveIntegerField(_('Retry count'), default=0, help_text=_('A number of delivery retries has already been made.'))
    message_cache = models.TextField(_('Message cache'), null=True, editable=False)
    dispatch_status = models.PositiveIntegerField(_('Dispatch status'), choices=DISPATCH_STATUSES, default=DISPATCH_STATUS_PENDING)
    read_status = models.PositiveIntegerField(_('Read status'), choices=READ_STATUSES, default=READ_STATUS_UNDREAD)

    @classmethod
    def log_dispatches_errors(cls, dispatches):
        entries = []
        for dispatch in dispatches:
            # Saving message cache for further usage.
            dispatch.save()
            entries = cls(dispatch=dispatch, error_log=dispatch.error_log)
        cls.objects.bulk_create(entries)

    @classmethod
    def set_dispatches_statuses(cls, **kwargs):
        filter_kwargs_map = {
            'sent': cls.DISPATCH_STATUS_SENT,
            'error': cls.DISPATCH_STATUS_ERROR,
            'failed': cls.DISPATCH_STATUS_FAILED,
            'pending': cls.DISPATCH_STATUS_PENDING,
        }
        for kwarg_name, status in filter_kwargs_map.items():
            if kwargs[kwarg_name]:
                update_kwargs = {
                    'time_dispatched': datetime.now(),
                    'dispatch_status': status,
                    'retry_count': models.F('retry_count') + 1
                }
                cls.objects.filter(id__in=[d.id for d in kwargs[kwarg_name]]).update(**update_kwargs)

    @staticmethod
    def group_by_messengers(dispatches):
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
        filter_kwargs = {
            'dispatch_status__in': (cls.DISPATCH_STATUS_PENDING, cls.DISPATCH_STATUS_ERROR)
        }
        if priority is not None:
            filter_kwargs['message__priority'] = priority
        return cls.objects.select_related('message').filter(**filter_kwargs).order_by('-message__time_created').all()

    @classmethod
    def get_unread(cls):
        return cls.objects.filter(read_status=cls.READ_STATUS_UNDREAD).select_related('message').all()

    @classmethod
    def create(cls, message_model, recipients):
        objects = []
        if recipients:
            if not hasattr(recipients, '__iter__'):
                recipients = (recipients,)

            for r in recipients:
                objects.append(cls(message=message_model, messenger=r.messenger, recipient=r.user, address=r.address))

            if objects:
                cls.objects.bulk_create(objects)

            if not message_model.dispatches_ready:
                message_model.dispatches_ready = True
                message_model.save()

        return objects

    class Meta:
        verbose_name = _('Dispatch')
        verbose_name_plural = _('Dispatches')

    def __str__(self):
        return '%s [%s]' % (self.address, self.messenger)


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