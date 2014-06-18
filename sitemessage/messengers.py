try:
    from django.contrib.auth import get_user_model
    USER_MODEL = get_user_model()
except ImportError:
    # Django 1.4 fallback.
    from django.contrib.auth.models import User as USER_MODEL
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.html import strip_tags

from .utils import MessengerBase
from .exceptions import MessengerWarmupException


class SMTPMessenger(MessengerBase):
    """Implements SMTP message delivery using Python builtin smtplib module."""

    alias = 'smtp'
    smtp = None
    _session_started = False

    def __init__(self, from_email=None, login=None, password=None, host=None, port=None, use_tls=None, use_ssl=None, debug=False):
        """Configures messenger.

        :param str from_email: e-mail address to send messages from
        :param str login: login to log into SMTP server
        :param str password: password to log into SMTP server
        :param str host: string - SMTP server host
        :param int port:  SMTP server port
        :param bool use_tls: whether to use TLS
        :param bool use_ssl: whether to use SSL
        :param bool debug: whether to switch smtplib into debug mode.
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

    @classmethod
    def get_address(cls, recipient):
        if hasattr(recipient, 'email'):
            recipient = recipient.email
        return recipient

    def _test_message(self, to, text):
        return self._send_message(self._build_message(to, text, mtype='html'))

    def before_send(self):
        try:
            self.smtp = self.lib.SMTP(self.host, self.port)
            self.smtp.set_debuglevel(self.debug)

            if self.use_tls:
                self.smtp.ehlo()
                if self.smtp.has_extn('STARTTLS'):
                    self.smtp.starttls()
                    self.smtp.ehlo()  # This time over TLS.

            if self.login:
                self.smtp.login(self.login, self.password)

            self._session_started = True
        except self.lib.SMTPException as e:
            raise MessengerWarmupException('SMTP Error: %s' % e)

    def after_send(self):
        self.smtp.quit()

    def _build_message(self, to, text, subject=None, mtype=None):
        """Constructs a MIME message from message and dispatch models."""
        # TODO Maybe file attachments handling through `files` message_model context var.

        if subject is None:
            subject = u'%s' % _('No Subject')

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

        return msg

    def _send_message(self, msg):
        return self.smtp.sendmail(msg['From'], msg['To'], msg.as_string())

    def send(self, message_cls, message_model, dispatch_models):
        if self._session_started:
            for dispatch_model in dispatch_models:

                msg = self._build_message(
                    dispatch_model.address,
                    dispatch_model.message_cache,
                    message_model.context.get('subject'),
                    message_model.context.get('type'),
                )

                try:
                    refused = self._send_message(msg)
                    if refused:
                        self.mark_failed(dispatch_model, '`%s` address is rejected by server' % msg['To'])
                        continue
                    self.mark_sent(dispatch_model)
                except Exception as e:
                    self.mark_error(dispatch_model, e, message_cls)


class XMPPSleekMessenger(MessengerBase):
    """Implements XMPP message delivery using `sleekxmpp` module."""

    alias = 'xmppsleek'
    xmpp = None
    _session_started = False

    def __init__(self, from_jid, password, host='localhost', port=5222, use_tls=True, use_ssl=False):
        """Configures messenger.

        :param str from_jid: Jabber ID to send messages from
        :param str password: password to log into XMPP server
        :param str host: XMPP server host
        :param int port: XMPP server port
        :param bool use_tls: whether to use TLS
        :param bool use_ssl: whether to use SSL
        :return:
        """
        import sleekxmpp

        self.lib = sleekxmpp

        self.from_jid = from_jid
        self.password = password
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def _test_message(self, to, text):
        return self._send_message(to, text)

    def _send_message(self, to, text):
        return self.xmpp.send_message(mfrom=self.from_jid, mto=to, mbody=text, mtype='chat')

    def before_send(self):
        def on_session_start(event):
            try:
                self.xmpp.send_presence()
                self.xmpp.get_roster()
                self._session_started = True
            except self.lib.exceptions.XMPPError as e:
                raise MessengerWarmupException('XMPP Error: %s' % e)

        self.xmpp = self.lib.ClientXMPP(self.from_jid, self.password)
        self.xmpp.add_event_handler('session_start', on_session_start)

        result = self.xmpp.connect(address=(self.host, self.port), reattempt=False, use_tls=self.use_tls, use_ssl=self.use_ssl)
        if result:
            self.xmpp.process(block=False)

    def after_send(self):
        if self._session_started:
            self.xmpp.disconnect(wait=True)  # Wait for a send queue.
            self._session_started = False

    def send(self, message_cls, message_model, dispatch_models):
        if self._session_started:
            for dispatch_model in dispatch_models:
                try:
                    self._send_message(dispatch_model.address, dispatch_model.message_cache)
                    self.mark_sent(dispatch_model)
                except Exception as e:
                    self.mark_error(dispatch_model, e, message_cls)
