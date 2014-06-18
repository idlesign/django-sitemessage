# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Message'
        db.create_table('sitemessage_message', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time_created', self.gf('django.db.models.fields.DateTimeField')(blank=True, auto_now_add=True)),
            ('sender', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, to=orm['apps.User'], null=True)),
            ('cls', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=250)),
            ('context', self.gf('sitemessage.models.ContextField')()),
            ('dispatches_ready', self.gf('django.db.models.fields.BooleanField')(db_index=True, default=False)),
        ))
        db.send_create_signal('sitemessage', ['Message'])

        # Adding model 'Dispatch'
        db.create_table('sitemessage_dispatch', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time_created', self.gf('django.db.models.fields.DateTimeField')(blank=True, auto_now_add=True)),
            ('time_dispatched', self.gf('django.db.models.fields.DateTimeField')(blank=True, null=True)),
            ('message', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['sitemessage.Message'])),
            ('messenger', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=250)),
            ('recipient', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, to=orm['apps.User'], null=True)),
            ('address', self.gf('django.db.models.fields.CharField')(max_length=250)),
            ('retry_count', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('message_cache', self.gf('django.db.models.fields.TextField')(null=True)),
            ('dispatch_status', self.gf('django.db.models.fields.PositiveIntegerField')(default=1)),
            ('read_status', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
        ))
        db.send_create_signal('sitemessage', ['Dispatch'])

        # Adding model 'DispatchError'
        db.create_table('sitemessage_dispatcherror', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('time_created', self.gf('django.db.models.fields.DateTimeField')(blank=True, auto_now_add=True)),
            ('dispatch', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['sitemessage.Dispatch'])),
            ('error_log', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('sitemessage', ['DispatchError'])


    def backwards(self, orm):
        # Deleting model 'Message'
        db.delete_table('sitemessage_message')

        # Deleting model 'Dispatch'
        db.delete_table('sitemessage_dispatch')

        # Deleting model 'DispatchError'
        db.delete_table('sitemessage_dispatcherror')


    models = {
        'apps.place': {
            'Meta': {'object_name': 'Place'},
            'geo_bounds': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'geo_pos': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '255', 'null': 'True'}),
            'geo_title': ('django.db.models.fields.TextField', [], {'blank': 'True', 'null': 'True'}),
            'geo_type': ('django.db.models.fields.CharField', [], {'blank': 'True', 'db_index': 'True', 'max_length': '25', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'raters_num': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'rating': ('django.db.models.fields.FloatField', [], {'db_index': 'True', 'default': '0'}),
            'status': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'time_created': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now_add': 'True'}),
            'time_modified': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now': 'True', 'null': 'True'}),
            'time_published': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'user_title': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'apps.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'blank': 'True', 'max_length': '75'}),
            'first_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'to': "orm['auth.Group']", 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'blank': 'True', 'max_length': '30'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'place': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['apps.Place']", 'related_name': "'users'", 'null': 'True'}),
            'raters_num': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'rating': ('django.db.models.fields.FloatField', [], {'db_index': 'True', 'default': '0'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'to': "orm['auth.Permission']", 'related_name': "'user_set'", 'symmetrical': 'False'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'blank': 'True', 'to': "orm['auth.Permission']", 'symmetrical': 'False'})
        },
        'auth.permission': {
            'Meta': {'object_name': 'Permission', 'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)"},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'contenttypes.contenttype': {
            'Meta': {'db_table': "'django_content_type'", 'object_name': 'ContentType', 'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'sitemessage.dispatch': {
            'Meta': {'object_name': 'Dispatch'},
            'address': ('django.db.models.fields.CharField', [], {'max_length': '250'}),
            'dispatch_status': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sitemessage.Message']"}),
            'message_cache': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'messenger': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '250'}),
            'read_status': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'recipient': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['apps.User']", 'null': 'True'}),
            'retry_count': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'time_created': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now_add': 'True'}),
            'time_dispatched': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'null': 'True'})
        },
        'sitemessage.dispatcherror': {
            'Meta': {'object_name': 'DispatchError'},
            'dispatch': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['sitemessage.Dispatch']"}),
            'error_log': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'time_created': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now_add': 'True'})
        },
        'sitemessage.message': {
            'Meta': {'object_name': 'Message'},
            'cls': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '250'}),
            'context': ('sitemessage.models.ContextField', [], {}),
            'dispatches_ready': ('django.db.models.fields.BooleanField', [], {'db_index': 'True', 'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sender': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'to': "orm['apps.User']", 'null': 'True'}),
            'time_created': ('django.db.models.fields.DateTimeField', [], {'blank': 'True', 'auto_now_add': 'True'})
        }
    }

    complete_apps = ['sitemessage']