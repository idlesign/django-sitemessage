Messengers
==========


`sitemessage` messenger classes implement clients for various protocols (smtp, jabber, etc.).

You can either use builtin classes or define your own.


Helper functions
----------------

.. automodule:: sitemessage.utils
    :members: register_messenger_objects, get_registered_messenger_objects, get_registered_messenger_object


Builtin messengers
------------------

Builtin messengers are available from **sitemessage.messengers**:


.. automodule:: sitemessage.messengers
   :members:


User defined messengers
-----------------------

To define a message type one needs to inherit from **sitemessage.utils.MessengerBase** (or a builtin messenger class),
and to register it with **sitemessage.utils.register_messenger_objects** (put these instructions
into `sitemessages.py` in one of your apps):


.. code-block:: python

    from .utils import MessengerBase, register_messenger_objects

    class MyMessenger(MessengerBase):

        # Messengers could be addressed by aliases.
        alias = 'mymessenger'

        def __init__(self):
            """This messenger doesn't accept any configuration arguments.
            Other may expect login, password, host, etc. to connect this messenger to a service.

            """
        @classmethod
        def get_address(cls, recipient):
            address = recipient
            if hasattr(recipient, 'username'):
                # We'll simply get address from User object `username`.
                address = '%s--address' % recipient.username
            return address

    def before_send(self):
        """We don't need that for now, but usually here will be messenger warm up (connect) code."""

    def after_send(self):
        """We don't need that for now, but usually here will be messenger cool down (disconnect) code."""

    def send(self, message_cls, message_model, dispatch_models):
        """This is the main sending method that every messenger must implement."""

        # `dispatch_models` from sitemessage are models representing a dispatch
        # of a certain message_model for a definite addressee.
        for dispatch_model in dispatch_models:

            # For demonstration purposes we won't send a dispatch anywhere,
            # we'll just mark it as sent:
            self.mark_sent(dispatch_model)  # See also: self.mark_failed() and self.mark_error().

    register_messenger_objects(MyMessenger())


.. note::

    Look through ``MessengerBase`` and other builtin messenger classes for more information and
    code examples.


After that you can schedule and send messages with your messenger as usual:

.. code-block:: python

    from sitemessage.toolbox import schedule_messages, recipients

    user2 = ...  # Let's suppose it's an instance of Django user model.
    # We'll just try to send PlainText message.
    schedule_messages('Some plain text message', recipients('mymessenger', ['user1--address', user2]))
