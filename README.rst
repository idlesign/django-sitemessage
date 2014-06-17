django-sitemessage
==================
https://github.com/idlesign/django-sitemessage

.. image:: https://badge.fury.io/py/django-sitemessage.png
    :target: http://badge.fury.io/py/django-sitemessage

.. image:: https://pypip.in/d/django-sitemessage/badge.png
        :target: https://crate.io/packages/django-sitemessage


Description
-----------

*Reusable application for Django introducing a message delivery framework*


Schedule and send messages with several easy steps, using concepts of:

* **Messengers** - clients for various protocols (smtp, jabber, etc.);

* **Message Types** - message classes exposing message composition logic (plain text, html, etc.).


1. Configure messengers for your project (create `sitemessages.py` in one of your apps):

    from sitemessage.utils import register_messenger_objects
    from sitemessage.messengers import SMTPMessenger

    register_messenger_objects(
        # Here we register only one messenger to deliver emails.
        SMTPMessenger('user1@host.com', 'user1', 'user1password', host='smtp.host.com', use_tls=True)
    )


2. Schedule messages for delivery when and where needed (e.g. in a view):

    from sitemessage.schortcuts import schedule_email

    def send_mail_view(request):
        ...

        # Suppose `user_model` is a recipient Django User model instance.
        user1_model = ...

        # We pass `request.user` into `sender` to keep track of senders.
        schedule_email('Message from sitemessage.', [user1_model, 'user2@host.com'], sender=request.user)

        ...


3. Periodically run Django management command from wherever you like (cli, cron, Celery, etc.):

    ./manage.py sitemessage_send_scheduled


And that's only the tip of `sitemessage` iceberg, read the docs %)


Documentation
-------------

http://django-sitemessage.readthedocs.org/