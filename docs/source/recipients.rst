Recipients and subscriptions
============================


Postponed dispatches
--------------------

Note that when scheduling a message you can omit `recipients` parameter.

In that case no dispatch objects are created on scheduling, instead the process of creation
is postponed until `prepare_dispatches()` function is called.


.. code-block:: python

    from sitemessage.toolbox import schedule_messages, prepare_dispatches

    # Here `recipients` parameter is omitted ...
    schedule_messages(MyMessage('Some text'))

    # ... instead dispatches are created later.
    prepare_dispatches()



`prepare_dispatches()` by default generates dispatches using recipients list comprised
from users subscription preferences data (see below).


Handling subscriptions
----------------------

**sitemessage** supports basic subscriptions mechanics, and that's how it works.


**sitemessage.toolbox.get_user_preferences_for_ui** is able to generate user subscription preferences data,
that could be rendered in HTML as table using **sitemessage_prefs_table** template tag.

.. note::

    **sitemessage_prefs_table** tag support table layout customization through custom templates.

    * **user_prefs_table-bootstrap.html** - Bootstrap-style table.

      {% sitemessage_prefs_table from subscr_prefs template "sitemessage/user_prefs_table-bootstrap.html" %}


This table in its turn could be placed in *form* tag to allow users to choose message types they want to receive
using various messengers.

At last **sitemessage.toolbox.set_user_preferences_from_request** can process *form* data from a request
and store subscription data into DB.


.. code-block:: python

    from django.shortcuts import render
    from sitemessage.toolbox import set_user_preferences_from_request, get_user_preferences_for_ui


    def user_preferences(self, request):
        """Let's suppose this simplified view handles user preferences."""

        ...

        if request.POST:
            # Process form data:
            set_user_preferences_from_request(request)
            ...

        # Prepare preferences data.
        subscr_prefs = get_user_preferences_for_ui(request.user)

        ...

        return render(request, 'user_preferences.html', {'subscr_prefs': subscr_prefs})



.. note::

    **get_user_preferences_for_ui** allows messenger titles customization and both
    message types and messengers filtering. You can also forbid subscriptions on message type
    or messenger level by setting `allow_user_subscription` class attribute to `False`.


And that's what is in a template used by the view above:

.. code-block:: html

    <!-- user_preferences.html -->
    {% load sitemessage %}

    <form method="post">
        {% csrf_token %}

        <!-- Create preferences table from `subscr_prefs` template variable. -->
        {% sitemessage_prefs_table from subscr_prefs %}

        <input type="submit" value="Save preferences" />
    </form>


.. note::

    You can get subscribers as recipients list right from your message type, using `get_subscribers()` method.


Handling unsubscriptions
------------------------

.. _handle_unsubscriptions:

**sitemessage** bundles some views, and one of those allows users to unsubscribe from certain message types
just by visiting it.

Please refer to :ref:`Bundled views <bundled_views>` section of this documentation.

After that, for example, your E-mail client (if it supports `List-Unsubscribe` header) will happily introduce you
some button to unsubscribe from messages of that type.
