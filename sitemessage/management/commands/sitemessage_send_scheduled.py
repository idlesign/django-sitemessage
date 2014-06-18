from optparse import make_option

from django.core.management.base import BaseCommand

from sitemessage.toolbox import send_scheduled_messages


class Command(BaseCommand):

    help = 'Sends scheduled messages (both in pending and error statuses).'

    option_list = BaseCommand.option_list + (
        make_option('--priority', action='store', dest='priority', default=None,
                    help='Allows to filter scheduled messages by a priority number. Defaults to None.'),
    )

    def handle(self, *args, **options):
        priority = options.get('priority', None)
        priority_str = ''

        if priority is not None:
            priority_str = 'with priority %s ' % priority

        self.stdout.write('Sending scheduled messages %s...\n' % priority_str)
        try:
            send_scheduled_messages(priority=priority)
        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on send: %s\n' % e))
        else:
            self.stdout.write('Sending done.\n')
