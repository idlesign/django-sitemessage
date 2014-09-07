Sitemessage for reusable applications
=====================================

``sitemessage`` offers reusable applications authors an API to send messages in a way that
can be customized by project authors.



For applications authors
------------------------


Use **sitemessage.toolbox.get_message_type_for_app** to return a registered message type object for your application.


.. note::

    Project authors can override the above mentioned object to customize messages.


.. code-block:: python

    from sitemessage.toolbox import get_message_type_for_app, schedule_messages, recipients


    def schedule_email(text, to, subject):
        """Suppose you're sending a notification and want to sent a plain text e-mail by default."""

        # This says: give me a message type `email_plain` if not overridden.
        message_cls = get_message_type_for_app('myapp', 'email_plain')
        message_obj = message_cls(subject, text)

        # And this actually schedules a message to send via `smtp` messenger.
        schedule_messages(message_obj, recipients('smtp', to))


.. note::

    It's advisable for reusable applications authors to document which message types are used
    in the app by default, with which arguments, so that project authors may design their
    custom message classes accordingly.



For project authors
-------------------

Use **sitemessage.toolbox.override_message_type_for_app** to override a given message type used by a certain application with a custom one.


.. note::

    You'd probably need to know which message types are used in an app by default, and with which arguments,
    so that you may design your custom message classes accordingly (e.g. by subclassing the default type).


.. code-block:: python

    from sitemessage.toolbox import override_message_type_for_app

    # This will override `email_plain` message type by `my_custom_email_plain` for `myapp` application.
    override_message_type_for_app('myapp', 'email_plain', 'my_custom_email_plain')


.. warning::

    Be sure to call ``override_message_type_for_app`` beforehand. So that to the moment when a thirdparty app
    will try to send a message, message type is overridden.
