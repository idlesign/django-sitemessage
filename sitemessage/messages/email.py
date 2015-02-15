from django.utils.translation import ugettext as _

from .base import MessageBase


class _EmailMessageBase(MessageBase):

    supported_messengers = ['smtp']
    title = _('Email notification')

    def __init__(self, subject, text_or_dict, type_name, template_path=None):
        context = {
            'subject': subject,
            'type': type_name,
        }
        self.update_context(context, text_or_dict)
        super(_EmailMessageBase, self).__init__(context, template_path=template_path)


class EmailTextMessage(_EmailMessageBase):
    """Simple plain text message to send as an e-mail."""

    alias = 'email_plain'
    template_ext = 'txt'

    def __init__(self, subject, text_or_dict, template_path=None):
        super(EmailTextMessage, self).__init__(subject, text_or_dict, 'plain', template_path=template_path)


class EmailHtmlMessage(_EmailMessageBase):
    """HTML message to send as an e-mail."""

    alias = 'email_html'
    template_ext = 'html'

    def __init__(self, subject, html_or_dict, template_path=None):
        super(EmailHtmlMessage, self).__init__(subject, html_or_dict, 'html', template_path=template_path)
