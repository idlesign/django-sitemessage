"""This file contains signals emitted by sitemessage."""
import django.dispatch


# Emitted when user unsubscribe requested is successful.
sig_unsubscribe_success = django.dispatch.Signal(providing_args=['request', 'message', 'dispatch'])

# Emitted when user unsubscribe requested fails.
sig_unsubscribe_failed = django.dispatch.Signal(providing_args=['request', 'message', 'dispatch'])

# Emitted when mark read requested is successful.
sig_mark_read_success = django.dispatch.Signal(providing_args=['request', 'message', 'dispatch'])

# Emitted when mark read requested fails.
sig_mark_read_failed = django.dispatch.Signal(providing_args=['request', 'message', 'dispatch'])
