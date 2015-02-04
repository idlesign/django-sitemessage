from django.core.mail.backends.base import BaseEmailBackend

from .shortcuts import schedule_email
from .settings import EMAIL_BACKEND_MESSAGES_PRIORITY


class EmailBackend(BaseEmailBackend):
    """Email backend for Django built-in mailing functions scheduling messages."""

    def send_messages(self, email_messages):
        if not email_messages:
            return

        sent = 0
        for message in email_messages:

            if not message.recipients():
                continue

            schedule_email(
                {'contents': message.body},
                message.recipients(),
                subject=message.subject, priority=EMAIL_BACKEND_MESSAGES_PRIORITY
            )

            sent += 1

        return sent
