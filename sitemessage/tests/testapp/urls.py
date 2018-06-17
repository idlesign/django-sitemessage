from django import VERSION

from sitemessage.toolbox import get_sitemessage_urls


urlpatterns = get_sitemessage_urls()

if VERSION < (1, 10):
    from django.conf.urls import patterns
    urlpatterns.insert(0, '')
    urlpatterns = patterns(*urlpatterns)
