import os
import sys

from setuptools import setup

from sitemessage import VERSION

PATH_BASE = os.path.dirname(__file__)
PYTEST_RUNNER = ['pytest-runner'] if 'test' in sys.argv else []

f = open(os.path.join(PATH_BASE, 'README.rst'))
README = f.read()
f.close()


setup(
    name='django-sitemessage',
    version='.'.join(map(str, VERSION)),
    url='https://github.com/idlesign/django-sitemessage',

    description='Reusable application for Django introducing a message delivery framework',
    long_description=README,
    license='BSD 3-Clause License',

    author='Igor `idle sign` Starikov',
    author_email='idlesign@yandex.ru',

    packages=['sitemessage'],
    include_package_data=True,
    zip_safe=False,

    install_requires=[
        'django-etc >= 1.2.0',
    ],
    setup_requires=[] + PYTEST_RUNNER,
    tests_require=[
        'pytest',
        'pytest-djangoapp>=0.10.0',
    ],

    classifiers=[
        # As in https://pypi.python.org/pypi?:action=list_classifiers
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: BSD License'
    ],
)

