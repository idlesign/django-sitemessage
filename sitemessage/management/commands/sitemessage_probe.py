from traceback import format_exc

from django.core.management.base import BaseCommand

from sitemessage.compat import CommandOption, options_getter
from sitemessage.toolbox import send_test_message


get_options = options_getter((
    CommandOption(
        '--to', action='store', dest='to', default=None,
        help='Recipient address (if supported by messenger).'
    ),
))


class Command(BaseCommand):

    help = 'Removes sent dispatches from DB.'

    option_list = get_options()
    args = '[messenger]'

    def add_arguments(self, parser):
        parser.add_argument('messenger', metavar='messenger', help='Messenger to test.')
        get_options(parser.add_argument)

    def handle(self, messenger, *args, **options):

        to = options.get('to', None)

        self.stdout.write('Sending test message using %s ...\n' % messenger)

        try:
            result = send_test_message(messenger, to=to)
            self.stdout.write('Probing function result: %s.\n' % result)

        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on probe: %s\n%s' % (e, format_exc())))

        else:
            self.stdout.write('Probing done.\n')
