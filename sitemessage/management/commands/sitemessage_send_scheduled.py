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
            priority_str = f'with priority {priority} '

        self.stdout.write(f'Sending scheduled messages {priority_str} ...\n')

        try:
            send_scheduled_messages(priority=priority)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error on send: {e}\n{format_exc()}'))

        else:
            self.stdout.write('Sending done.\n')
