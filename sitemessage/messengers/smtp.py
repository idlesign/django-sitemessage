from django.conf import settings
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from .base import MessengerBase
from ..exceptions import MessengerWarmupException


class SMTPMessenger(MessengerBase):
    """Implements SMTP message delivery using Python builtin smtplib module."""

    alias = 'smtp'
    smtp = None
    title = _('E-mail')

    address_attr = 'email'

    _session_started = False

    def __init__(
            self, from_email=None, login=None, password=None, host=None, port=None,
            use_tls=None, use_ssl=None, debug=False, timeout=None):
        """Configures messenger.

        :param str from_email: e-mail address to send messages from
        :param str login: login to log into SMTP server
        :param str password: password to log into SMTP server
        :param str host: string - SMTP server host
        :param int port:  SMTP server port
        :param bool use_tls: whether to use TLS
        :param bool use_ssl: whether to use SSL
        :param bool debug: whether to switch smtplib into debug mode.
        :param int timeout: timeout to establish s connection.

        """
        import smtplib

        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        self.debug = debug
        self.lib = smtplib
        self.mime_text = MIMEText
        self.mime_multipart = MIMEMultipart

        self.from_email = from_email or getattr(settings, 'SERVER_EMAIL')
        self.login = login or getattr(settings, 'EMAIL_HOST_USER')
        self.password = password or getattr(settings, 'EMAIL_HOST_PASSWORD')
        self.host = host or getattr(settings, 'EMAIL_HOST')
        self.port = port or getattr(settings, 'EMAIL_PORT')
        self.use_tls = use_tls or getattr(settings, 'EMAIL_USE_TLS')
        self.use_ssl = use_ssl or getattr(settings, 'EMAIL_USE_SSL', False)  # False as default to support Django < 1.7
        self.timeout = timeout or getattr(settings, 'EMAIL_TIMEOUT', None)  # None as default to support Django < 1.8

    def _test_message(self, to, text):
        return self._send_message(self._build_message(to, text, mtype='html'))

    def before_send(self):
        lib = self.lib

        try:
            smtp_cls = lib.SMTP_SSL if self.use_ssl else lib.SMTP
            kwargs = {}
            timeout = self.timeout

            if timeout:
                kwargs['timeout'] = timeout

            smtp = smtp_cls(self.host, self.port, **kwargs)

            self.smtp = smtp

            smtp.set_debuglevel(self.debug)

            if self.use_tls:
                smtp.ehlo()
                if smtp.has_extn('STARTTLS'):
                    smtp.starttls()
                    smtp.ehlo()  # This time over TLS.

            if self.login:
                smtp.login(self.login, self.password)

            self._session_started = True

        except lib.SMTPException as e:
            raise MessengerWarmupException(f'SMTP Error: {e}')

    def after_send(self):
        self.smtp.quit()

    def _build_message(self, to, text, subject=None, mtype=None, unsubscribe_url=None):
        """Constructs a MIME message from message and dispatch models."""
        # TODO Maybe file attachments handling through `files` message_model context var.

        if subject is None:
            subject = '%s' % _('No Subject')

        if mtype == 'html':
            msg = self.mime_multipart()
            text_part = self.mime_multipart('alternative')
            text_part.attach(self.mime_text(strip_tags(text), _charset='utf-8'))
            text_part.attach(self.mime_text(text, 'html', _charset='utf-8'))
            msg.attach(text_part)

        else:
            msg = self.mime_text(text, _charset='utf-8')

        msg['From'] = self.from_email
        msg['To'] = to
        msg['Subject'] = subject

        if unsubscribe_url:
            msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'

        return msg

    def _send_message(self, msg):
        return self.smtp.sendmail(msg['From'], msg['To'], msg.as_string())

    def send(self, message_cls, message_model, dispatch_models):

        if not self._session_started:
            return

        for dispatch_model in dispatch_models:

            msg = self._build_message(
                dispatch_model.address,
                dispatch_model.message_cache,
                message_model.context.get('subject'),
                message_model.context.get('type'),
                message_cls.get_unsubscribe_directive(message_model, dispatch_model)
            )

            try:
                refused = self._send_message(msg)

                if refused:
                    self.mark_failed(dispatch_model, f"`{msg['To']}` address is rejected by server")
                    continue

                self.mark_sent(dispatch_model)

            except Exception as e:
                self.mark_error(dispatch_model, e, message_cls)
