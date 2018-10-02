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
            suffix.append('sent %s days ago' % ago)

        self.stdout.write('Cleaning up dispatches %s ...\n' % ' '.join(suffix))

        try:
            cleanup_sent_messages(ago=ago, dispatches_only=dispatches_only)

        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on cleanup: %s\n%s' % (e, format_exc())))

        else:
            self.stdout.write('Cleanup done.\n')
