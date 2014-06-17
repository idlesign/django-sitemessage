from .messages import EmailHtmlMessage, EmailTextMessage
from .toolbox import schedule_messages, recipients


def schedule_email(message, to, subject=None, sender=None):
    '''Schedules an email message for delivery.

    :param message: str or dict: use str for simple text email; dict - to compile email from a template (default: `sitemessage/email_html_smtp.html`).
    :param to: list - recipients addresses or Django User model heir instances
    :param subject: string - email subject
    :param sender: User - model heir instance
    '''
    if isinstance(message, dict):
        message_cls = EmailHtmlMessage
    else:
        message_cls = EmailTextMessage
    schedule_messages(message_cls(subject, message), recipients('smtp', to), sender=sender)


def schedule_jabber_message(message, to, sender=None):
    '''Schedules an email message for delivery.

    :param message: str - text to send.
    :param to: list - recipients addresses or Django User model heir instances
    :param sender: User - model heir instance
    '''
    schedule_messages(message, recipients('xmppsleek', to), sender=sender)
