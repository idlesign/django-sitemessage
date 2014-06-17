from django.core.management.base import BaseCommand

from sitemessage.toolbox import send_scheduled_messages


class Command(BaseCommand):

    help = 'Sends scheduled messages (both in pending and error statuses).'

    def handle(self, *apps, **options):
        self.stdout.write('Sending scheduled messages...\n')
        try:
            send_scheduled_messages()
        except Exception as e:
            self.stderr.write(self.style.ERROR('Error on send: %s\n' % e))
        else:
            self.stdout.write('Sending done.\n')
