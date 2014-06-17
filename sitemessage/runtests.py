#! /usr/bin/env python
import sys
import os

from django.conf import settings


def main():
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

    app_name = 'sitemessage'

    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=('django.contrib.auth', 'django.contrib.contenttypes', app_name),
            DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}},
        )

    from django.test.utils import get_runner
    runner = get_runner(settings)()
    failures = runner.run_tests((app_name,))

    sys.exit(failures)


if __name__ == '__main__':
    main()
