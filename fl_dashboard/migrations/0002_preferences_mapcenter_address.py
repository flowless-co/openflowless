# Generated by Django 2.2.1 on 2020-01-09 18:13

from django.db import migrations
import django_google_maps.fields


class Migration(migrations.Migration):

    dependencies = [
        ('fl_dashboard', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='preferences',
            name='mapCenter_address',
            field=django_google_maps.fields.AddressField(default='', max_length=80),
        ),
    ]
