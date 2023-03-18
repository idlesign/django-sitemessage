django-sitemessage documentation
================================
https://github.com/idlesign/django-sitemessage



Description
-----------

*Reusable application for Django introducing a message delivery framework.*

Features:

* **Message Types** - message classes exposing message composition logic (plain text, html, etc.).
* **Messengers** - clients for various protocols (smtp, jabber, twitter, telegram, facebook, vkontakte, etc.);
* Support for user defined message types.
* Support for user defined messenger types.
* Message prioritization.
* Message subscription/unsubscription system.
* Message grouping to prevent flooding.
* Message 'read' indication.
* Means for background message delivery and cleanup.
* Means to debug integration: test requisites, delivery log.
* Django Admin integration.

Currently supported messengers:

1. SMTP;
2. XMPP (requires ``sleekxmpp`` package);
3. Twitter (requires ``twitter`` package);
4. Telegram (requires ``requests`` package);
5. Facebook (requires ``requests`` package);
6. VKontakte (requires ``requests`` package).



Requirements
------------

1. Python 3.7+
2. Django 2.0+



Table of Contents
-----------------

.. toctree::
    :maxdepth: 2

    quickstart
    toolbox
    messages
    messengers
    exceptions
    prioritizing
    grouping
    recipients
    views
    apps


Get involved into django-sitemessage
------------------------------------

**Submit issues.** If you spotted something weird in application behavior or want to propose a feature you can do
that at https://github.com/idlesign/django-sitemessage/issues

**Write code.** If you are eager to participate in application development, fork it
at https://github.com/idlesign/django-sitemessage, write your code, whether it should be a bugfix or a feature
implementation, and make a pull request right from the forked project page.

**Translate.** If want to translate the application into your native language use Transifex:
https://www.transifex.net/projects/p/django-sitemessage/.

**Spread the word.** If you have some tips and tricks or any other words in mind that you think might be of interest
for the others — publish it.


Also
----

If the application is not what you want for messaging with Django, you might be interested in considering
other choices at https://www.djangopackages.com/grids/g/notification/ or https://www.djangopackages.com/grids/g/newsletter/ 
or https://www.djangopackages.com/grids/g/email/.
