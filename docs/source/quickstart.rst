Quickstart
==========

* Add the **sitemessage** application to INSTALLED_APPS in your settings file (usually 'settings.py').
* Run './manage.py syncdb' to install `sitemessage` tables into database.


.. note::

    When switching from an older version do not forget to upgrade your database schema.

    That could be done with the following command issued in your Django project directory::

        ./manage.py migrate


1. Configure messengers for your project (create ``sitemessages.py`` in one of your apps):

    .. code-block:: python

        from sitemessage.toolbox import register_messenger_objects
        from sitemessage.messengers.smtp import SMTPMessenger
        from sitemessage.messengers.xmpp import XMPPSleekMessenger


        # We register two messengers to deliver emails and jabber messages.
        register_messenger_objects(
            SMTPMessenger('user1@host.com', 'user1', 'user1password', host='smtp.host.com', use_tls=True),
            XMPPSleekMessenger('user1@jabber.host.com', 'user1password', 'jabber.host.com'),
        )

        # Or you may want to define your own message type for further usage.
        class MyMessage(MessageBase):

            alias = 'myxmpp'
            supported_messengers = ['xmppsleek']

            @classmethod
            def create(cls, message: str):
                cls(message).schedule(cls.recipients('xmppsleek', ['a@some.tld', 'b@some.tld', ]))

        register_message_types(MyMessage)


2. Schedule messages for delivery when and where needed (e.g. in a view):

    .. code-block:: python

        from sitemessage.shortcuts import schedule_email, schedule_jabber_message
        from .sitemessages import MyFbMessage


        def send_messages_view(request):
            ...
            # Suppose `user_model` is a recipient User Model instance.
            user1_model = ...

            # Schedule both email and jabber messages to delivery.
            schedule_email('Email from sitemessage.', [user1_model, 'user2@host.com'])
            schedule_jabber_message('Jabber message from sitetree', ['user1@jabber.host.com', 'user2@jabber.host.com'])
            ...

            # Or if you want to send your message type:
            MyMessage.create('Hi there!')


3. Periodically run Django management command from wherever you like (cli, cron, Celery, uWSGI, etc.)::

    ./manage.py sitemessage_send_scheduled
