from traceback import format_exc

from django.core.management.base import BaseCommand

from sitemessage.compat import CommandOption, options_getter
from sitemessage.toolbox import send_scheduled_messages


get_options = options_getter((
    CommandOption(
        '--priority', action='store', dest='priority', default=None,
        help='Allows to filter scheduled messages by a priority number. Defaults to None.'
    ),
))


class Command(BaseCommand):

    help = 'Sends scheduled messages (both in pending and error statuses).'

    option_list = get_options()

    def add_arguments(self, parser):
        get_options(parser.add_argument)

    def handle(self, *args, **options):
        priority = options.get('priority', None)
        priority_str = ''

        if priority is not None:
            priority_str = 'with priority %s ' % priority

        self.stdout.write('Sending scheduled messages %s ...\n' % priority_str)

        try:
            send_scheduled_messages(priority=priority)

        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on send: %s\n%s' % (e, format_exc())))

        else:
            self.stdout.write('Sending done.\n')
