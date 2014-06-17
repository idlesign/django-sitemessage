from .utils import MessageBase, register_message_types


class PlainTextMessage(MessageBase):
    """Simple plain text message class to allow schedule_messages()
    to accept message as a simple string instead of a message object.

    """

    alias = 'plain'

    def __init__(self, text):
        super(PlainTextMessage, self).__init__({self.SIMPLE_TEXT_ID: text})


class _EmailMessageBase(MessageBase):

    supported_messengers = ['smtp']

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


def register_builtin_message_types():
    """Registers the built-in message types."""
    register_message_types(PlainTextMessage, EmailTextMessage, EmailHtmlMessage)


register_builtin_message_types()
