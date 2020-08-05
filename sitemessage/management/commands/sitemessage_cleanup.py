from traceback import format_exc

from django.core.management.base import BaseCommand

from sitemessage.compat import CommandOption, options_getter
from sitemessage.toolbox import cleanup_sent_messages


get_options = options_getter((
    CommandOption(
        '--ago', action='store', dest='ago', default=None, type=int,
        help='Allows cleanup messages sent X days ago. Defaults to None (cleanup all sent).'
    ),
    CommandOption('--dispatches_only', action='store_false', dest='dispatches_only', default=False,
                  help='Remove dispatches only (messages objects will stay intact).'),
))


class Command(BaseCommand):

    help = 'Removes sent dispatches from DB.'

    option_list = get_options()

    def add_arguments(self, parser):
        get_options(parser.add_argument)

    def handle(self, *args, **options):

        ago = options.get('ago', None)
        dispatches_only = options.get('dispatches_only', False)

        suffix = []

        if not dispatches_only:
            suffix.append('and messages')

        if ago:
            suffix.append(f'sent {ago} days ago')

        self.stdout.write(f"Cleaning up dispatches {' '.join(suffix)} ...\n")

        try:
            cleanup_sent_messages(ago=ago, dispatches_only=dispatches_only)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error on cleanup: {e}\n{format_exc()}'))

        else:
            self.stdout.write('Cleanup done.\n')
