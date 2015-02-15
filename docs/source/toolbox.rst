Toolbox
=======

`sitemessage` toolbox exposes some commonly used functions.


Defining message recipients
---------------------------

**sitemessage.toolbox.recipients** allows to define message recipients for various messengers,
so that they could be passed into message scheduling functions:

.. code-block:: python

    from sitemessage.toolbox import recipients
    from sitemessage.messengers.smtp import SMTPMessenger
    from sitemessage.messengers.xmpp import XMPPSleekMessenger


    # The first argument could be Messenger alias:
    my_smtp_recipients = recipients('smtp', ['user1@host.com', 'user2@host.com']),

    # or a Messenger class itself:
    my_jabber_recipients = recipients(XMPPSleekMessenger, ['user1@jabber.host.com', 'user2@jabber.host.com']),

    # Second arguments accepts either Django User model instance or an actual address:
    user1_model = ...
    my_smtp_recipients = recipients(SMTPMessenger, [user1_model, 'user2@host.com'])

    # You can also merge recipients from several messengers:
    my_recipients = my_smtp_recipients + my_jabber_recipients



Scheduling messages
-------------------

**sitemessage.toolbox.schedule_messages** is a generic tool to schedule messages:


.. code-block:: python

    from sitemessage.toolbox import schedule_messages, recipients
    # Let's import a built-in message type class we'll use.
    from sitemessage.messages import EmailHtmlMessage


    schedule_messages(
        # You can pass one or several message objects:
        [
            # The first param of this Message Type is `subject`. The second may be either an html itself:
            EmailHtmlMessage('Message subject 1', '<html><head></head><body>Some <b>text</b></body></html>'),

            # or a dictionary
            EmailHtmlMessage('Message subject 2', {'title': 'My message', 'entry': 'Some text.'}),

            # NOTE: Different Message Types may expect different arguments.
        ],

        # The same applies to recipients: add one or many as required:
        recipients('smtp', ['user1@host.com', 'user2@host.com']),

        # It's useful sometimes to know message sender in terms of Django users:
        sender=request.user
    )



Sending messages
----------------

Scheduled messages are normally sent with the help of **sitemessage_send_scheduled** management command, that
could be issued from wherever you like (cron, Celery, etc.)::

    ./manage.py sitemessage_send_scheduled


Nevertheless you can directly use **sitemessage.toolbox.send_scheduled_messages** from sitemessage toolbox:

.. code-block:: python

    from sitemessage.toolbox import send_scheduled_messages


    # Note that this might eventually raise UnknownMessengerError, UnknownMessageTypeError exceptions.
    send_scheduled_messages()

    # Or if you do not want sitemessage exceptions to be raised (that way scheduled messages
    # with unknown message types or for which messengers are not configured won't be sent):
    send_scheduled_messages(ignore_unknown_messengers=True, ignore_unknown_message_types=True)

    # To send only messages of a certain priority use `priority` argument.
    send_scheduled_messages(priority=10)
