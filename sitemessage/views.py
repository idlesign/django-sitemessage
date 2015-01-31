from django.shortcuts import redirect

from .models import Dispatch
from .exceptions import UnknownMessageTypeError
from .signals import sig_unsubscribe_failed


def unsubscribe(request, message_id, dispatch_id, hashed, redirect_to=None):

    if redirect_to is None:
        redirect_to = '/'

    try:
        dispatch = Dispatch.objects.select_related('message').get(pk=dispatch_id)
        message = dispatch.message
    except Dispatch.DoesNotExist:
        pass
    else:
        try:
            message_type = message.get_type()
            expected_hash = message_type.get_dispatch_hash(dispatch_id, message_id)

            return message_type.handle_unsubscribe_request(
                request, message, dispatch,
                hash_is_valid=(expected_hash == hashed),
                redirect_to=redirect_to
            )
        except UnknownMessageTypeError:
            pass

    sig_unsubscribe_failed.send(None, request=request, message=message_id, dispatch=dispatch_id)

    return redirect(redirect_to)
