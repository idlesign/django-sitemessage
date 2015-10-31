Quickstart
==========

* Add the **sitemessage** application to INSTALLED_APPS in your settings file (usually 'settings.py').
* Run './manage.py syncdb' to install `sitemessage` tables into database.


.. note::

    When switching from an older version do not forget to upgrade your database schema.

    That could be done with the following command issued in your Django project directory::

        ./manage.py migrate

    Note that the command **requires** `South <http://south.aeracode.org/>`_.

.. warning::

    If you are using a version Django < 1.7 AND are using a version of South < 1.0, add this to your settings:

    .. code-block:: python

        SOUTH_MIGRATION_MODULES = {
            'sitemessage': 'sitemessage.south_migrations',
        }


1. Configure messengers for your project (create `sitemessages.py` in one of your apps):

    .. code-block:: python

        from sitemessage.toolbox import register_messenger_objects, register_builtin_message_types
        from sitemessage.messengers.smtp import SMTPMessenger
        from sitemessage.messengers.xmpp import XMPPSleekMessenger


        # We register two messengers to deliver emails and jabber messages.
        register_messenger_objects(
            SMTPMessenger('user1@host.com', 'user1', 'user1password', host='smtp.host.com', use_tls=True),
            XMPPSleekMessenger('user1@jabber.host.com', 'user1password', 'jabber.host.com'),
        )

        # And register built-in message types we'd use (for Django < 1.7):
        register_builtin_message_types()


2. Schedule messages for delivery when and where needed (e.g. in a view):

    .. code-block:: python

        from sitemessage.shortcuts import schedule_email, schedule_jabber_message


        def send_messages_view(request):
            ...
            # Suppose `user_model` is a recipient User Model instance.
            user1_model = ...

            # Schedule both email and jabber messages to delivery.
            schedule_email('Email from sitemessage.', [user1_model, 'user2@host.com'])
            schedule_jabber_message('Jabber message from sitetree', ['user1@jabber.host.com', 'user2@jabber.host.com'])
            ...


3. Periodically run Django management command from wherever you like (cli, cron, Celery, etc.)::

    ./manage.py sitemessage_send_scheduled
