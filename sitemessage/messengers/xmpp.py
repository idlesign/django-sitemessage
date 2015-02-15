from django.utils.translation import ugettext as _

from .base import MessengerBase
from ..exceptions import MessengerWarmupException


class XMPPSleekMessenger(MessengerBase):
    """Implements XMPP message delivery using `sleekxmpp` module.

    http://sleekxmpp.com/

    """

    alias = 'xmppsleek'
    xmpp = None
    title = _('XMPP')
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

    @classmethod
    def get_address(cls, recipient):
        return getattr(recipient, 'jabber', None) or recipient

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
