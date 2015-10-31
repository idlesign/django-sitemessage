Messages
========


`sitemessage` message classes expose message composition logic (plain text, html, etc.).

You can either use builtin classes or define your own.


Helper functions
----------------

* **sitemessage.toolbox.register_message_types(\*message_types)**

  Registers message types (classes).

* **get_registered_message_types()**

  Returns registered message types dict indexed by their aliases.

* **get_registered_message_type(message_type)**

  Returns registered message type (class) by alias,



Builtin message types
---------------------

Builtin message types are available from **sitemessage.messages**:

* **sitemessage.messages.plain.PlainTextMessage**

* **sitemessage.messages.email.EmailTextMessage**

* **sitemessage.messages.email.EmailHtmlMessage**



User defined message types
--------------------------

To define a message type one needs to inherit from **sitemessage.messages.base.MessageBase** (or a builtin message class),
and to register it with **sitemessage.toolbox.register_message_types** (put these instructions
into `sitemessages.py` in one of your apps):


.. code-block:: python

    from sitemessage.messages.base import MessageBase
    from sitemessage.toolbox import register_message_types
    from django.utils import timezone


    class MyMessage(MessageBase):

        # Message types could be addressed by aliases.
        alias = 'mymessage'

        # Message type title to show up in UI
        title = 'Super message'

        # Define a template path to build messages from.
        # You can omit this setting and place your template under
        # `templates/sitemessage/messages/` naming it as `mymessage__<messenger>.html`
        # where <messenger> is a messenger alias, e.g. `smtp`.
        template = 'mymessages/mymessage.html'

        # Define a send retry limit for that message type.
        send_retry_limit = 10

        # If we don't want users to subscribe for messages of this type
        # (see get_user_preferences_for_ui()) we just forbid such subscriptions.
        allow_user_subscription = False

        def __init__(self, text, date):
            # Calling base class __init__ and passing message context
            super(MyMessage, self).__init__({'text': text, 'date': date})

        @classmethod
        def get_template_context(cls, context):
            """Here we can add some data into template context
            right before rendering.

            """
            context.update({'greeting': 'Hi!'})
            return context

        @classmethod
        def create(cls, text):
            """Let it be an alternative constructor - kind of a shortcut."""

            # This recipient list is comprised of users subscribed to this message type.
            recipients = cls.get_subscribers()

            # Or we can build recipient list for a certain messenger manually.
            # recipients = cls.recipients('smtp', 'someone@sowhere.local')

            date_now = timezone.now().date().strftime('%d.%m.%Y')
            cls(text, date_now).schedule(recipients)

    register_message_types(MyMessage)


.. note::

    Look through ``MessageBase`` and other builtin message classes for more code examples.


Now, as long as our message type uses a template, let's create it (`mymessages/mymessage.html`):

.. code-block:: html

    <!DOCTYPE html>
    <html>
    <head lang="en">
        <meta charset="UTF-8">
        <title>{{ greeting }}</title>
    </head>
    <body>
        <h1>{{ greeting }}</h1>
        {{ text }}
        <hr>
        {{ date }}
    </body>
    </html>


.. note::

    The following context variables are available in templates by default:

    **SITE_URL** - base site URL

    **message_model** - message model data

    **dispatch_model** - message dispatch model data

    **directive_unsubscribe** - unsubscribe directive string (e.g. URL, command)

    **directive_mark_read** - mark dispatch as read directive string (e.g. Url, command)



After that you can schedule and send messages of this new type:

.. code-block:: python

    from sitemessage.toolbox import schedule_messages, recipients
    from myproject.sitemessages import MyMessage


    # Scheduling message send via smtp.
    schedule_messages(MyMessage('Some text', '17.06.2014'), recipients('smtp', 'user1@host.com'))

    # Or we can use out shortcut method:
    MyMessage.create('Some other text')
