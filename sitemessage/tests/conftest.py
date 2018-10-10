from pytest_djangoapp import configure_djangoapp_plugin


pytest_plugins = configure_djangoapp_plugin({
    'ADMINS': [('one', 'a@a.com'), ('two', 'b@b.com')]
})
