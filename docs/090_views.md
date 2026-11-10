Bundled views
=============

.. _bundled_views:

**sitemessage** bundles some views, and one of those allows users to unsubscribe from certain message types,
or mark messages read just by visiting pages linked to those views. So let's configure your project to use those views:


.. code-block:: python

    from sitemessage.toolbox import get_sitemessage_urls

    ...

    # Somewhere in your urls.py.

    urlpatterns += get_sitemessage_urls()  # Attaching sitemessage URLs.



Unsubscribe
-----------

Read :ref:`Handling unsubscriptions <handle_unsubscriptions>` to get some information on how unsubscription works.


Mark read
---------

When bundled views are attached to your app you can mark messages as read.

For example if you put the following code in your HTML e-mail message template, the message dispatch in your DB
will be marked read as soon as Mail Client will render `<img>` tag.

.. code-block:: django+html

    {% if directive_mark_read %}
        <img src="{{ directive_mark_read }}">
    {% endif %}


This allows to track whether a user has read a message.
