from traceback import format_exc

from django.core.management.base import BaseCommand

from sitemessage.compat import CommandOption, options_getter
from sitemessage.toolbox import check_undelivered


get_options = options_getter((
    CommandOption(
        '--to', action='store', dest='to', default=None,
        help='Recipient e-mail. If not set Django ADMINS setting is used.'
    ),
))


class Command(BaseCommand):

    help = 'Sends a notification email if any undelivered dispatches.'

    option_list = get_options()

    def add_arguments(self, parser):
        get_options(parser.add_argument)

    def handle(self, *args, **options):

        to = options.get('to', None)

        self.stdout.write('Checking for undelivered dispatches ...\n')

        try:
            undelivered_count = check_undelivered(to=to)

            self.stdout.write('Undelivered dispatches count: %s.\n' % undelivered_count)

        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on check: %s\n%s' % (e, format_exc())))

        else:
            self.stdout.write('Check done.\n')
