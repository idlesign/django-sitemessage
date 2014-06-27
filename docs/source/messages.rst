Messages
========


`sitemessage` message classes expose message composition logic (plain text, html, etc.).

You can either use builtin classes or define your own.


Helper functions
----------------

* **sitemessage.utils.register_message_types(\*message_types)**

  Registers message types (classes).

* **get_registered_message_types()**

  Returns registered message types dict indexed by their aliases.

* **get_registered_message_type(message_type)**

  Returns registered message type (class) by alias,



Builtin message types
---------------------

Builtin message types are available from **sitemessage.messages**:

* **sitemessage.messages.PlainTextMessage**

* **sitemessage.messages.EmailTextMessage**

* **sitemessage.messages.EmailHtmlMessage**



User defined message types
--------------------------

To define a message type one needs to inherit from **sitemessage.utils.MessageBase** (or a builtin message class),
and to register it with **sitemessage.utils.register_message_types** (put these instructions
into `sitemessages.py` in one of your apps):


.. code-block:: python

    from .utils import MessageBase, register_message_types

    class MyMessage(MessageBase):

        # Message types could be addressed by aliases.
        alias = 'mymessage'

        # Let's do some optional tune up:

        # Define a template to build messages from.
        template = 'mymessages/mymessage.html'

        # Define a send retry limit for that message type.
        send_retry_limit = 10

        def __init__(self, text, date):
            # Calling base class __init__ and passing message context
            super(MyMessage, self).__init__({'text': text, 'date': date})

    register_message_types(MyMessage)


.. note::

    Look through ``MessageBase`` and other builtin message classes for more information and
    code examples.


Now, as long as our message type uses a temple, let's create it (`mymessages/mymessage.html`):

.. code-block:: html

    <!DOCTYPE html>
    <html>
    <head lang="en">
        <meta charset="UTF-8">
        <title>{{ date }}</title>
    </head>
    <body>
        Hello,

        {{ text }}

        <br/>
        ---
        {{ date }}
    </body>
    </html>


.. note::

    Message model data is available in templates under **message_model** variable.

    Message dispatch data is available in templates under **dispatch_model** variable.



After that you can schedule and send messages of you new type as usual:

.. code-block:: python

    from sitemessage.toolbox import schedule_messages, recipients
    from myproject.sitemessages import MyMessage

    # We'll just try to send message using smtp.
    schedule_messages(MyMessage('Some text', '2014-06-17'), recipients('smtp', 'user1@host.com'))

