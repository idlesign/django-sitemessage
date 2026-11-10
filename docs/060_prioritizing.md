Prioritizing messages
=====================

**sitemessage** supports message sending prioritization: any message might be given
a positive number to describe its priority.

.. note::

    It's up to you to decide the meaning of priority numbers.


Prioritization is supported on the following two levels:


1. You can define `priority` within your message type class.

.. code-block:: python

    from sitemessage.messages.base import MessageBase


    class MyMessage(MessageBase):

        alias = 'mymessage'

        priority = 10  # Messages of this type will automatically have priority of 10.

        ...


2. Or you can override priority defined within message type, by supplying `priority` argument
to messages scheduling functions.

.. code-block:: python

    from sitemessage.shortcuts import schedule_email
    from sitemessage.toolbox import schedule_messages, recipients


    schedule_email('Email from sitemessage.', 'user2@host.com', priority=1)

    # or

    schedule_messages('My message', recipients('smtp', 'user1@host.com'), priority=16)



After that you can use **sitemessage_send_scheduled** management command with **--priority**
argument to send message when needed::

    ./manage.py sitemessage_send_scheduled --priority 10


.. note::

    Use a scheduler (e.g cron, uWSGI cron/cron2, etc.) to send messages with different priorities
    on different days or intervals, and even simultaneously.
