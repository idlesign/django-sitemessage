Grouping messages
=================

**sitemessage** allows you to group messages in such a way that even if your application
generates many messages (between send attempts) your user receives them as one.


.. code-block:: python

    from sitemessage.messages.base import MessageBase


    class MyMessage(MessageBase):

        ...

        # Define group ID at class level or as a @property
        group_mark = 'groupme'

        # In case your message has some complex context
        # you may want to override 'merge_context' to add a new message
        # context to the context already existing in message stored in DB
        @classmethod
        def merge_context(cls, context: dict, new_context: dict) -> dict:
            merged = ...  #
            return merged

