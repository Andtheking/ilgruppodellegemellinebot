"""Peewee migrations -- 002_create_events.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    migrator.change_fields('chat', id=pw.BigIntegerField(primary_key=True))

    @migrator.create_model
    class EventSerie(pw.Model):
        id = pw.AutoField()
        chat = pw.ForeignKeyField(column_name='chat_id', field='id', model=migrator.orm['chat'])
        title = pw.TextField()
        default_event_time = pw.TimeField()
        default_remind_time = pw.TimeField()
        day_of_week = pw.SmallIntegerField()
        start_date = pw.DateField()
        end_date = pw.DateField()
        is_active = pw.BooleanField(default=True)

        class Meta:
            table_name = "eventserie"

    @migrator.create_model
    class ActualEvent(pw.Model):
        id = pw.AutoField()
        event_serie = pw.ForeignKeyField(column_name='event_serie_id', field='id', model=migrator.orm['eventserie'], on_delete='CASCADE')
        event_datetime = pw.DateTimeField()
        remind_datetime = pw.DateTimeField()
        status = pw.TextField(default='PENDING')
        note = pw.TextField(null=True)

        class Meta:
            table_name = "actualevent"
            indexes = [(('status', 'remind_datetime'), False)]

    @migrator.create_model
    class User(pw.Model):
        id = pw.BigIntegerField(primary_key=True)
        username = pw.TextField(null=True)
        admin = pw.BooleanField(default=False)

        class Meta:
            table_name = "user"

    @migrator.create_model
    class EventSerieSubscription(pw.Model):
        event_serie = pw.ForeignKeyField(column_name='event_serie_id', field='id', model=migrator.orm['eventserie'], on_delete='CASCADE')
        user = pw.ForeignKeyField(column_name='user_id', field='id', model=migrator.orm['user'], on_delete='CASCADE')

        class Meta:
            table_name = "eventseriesubscription"
            primary_key = pw.CompositeKey('event_serie', 'user')

    migrator.remove_model('utente')


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.change_fields('chat', id=pw.IntegerField(primary_key=True))

    @migrator.create_model
    class Utente(pw.Model):
        id = pw.IntegerField(primary_key=True)
        username = pw.TextField(null=True)
        admin = pw.BooleanField(default=False)

        class Meta:
            table_name = "utente"

    migrator.remove_model('eventseriesubscription')

    migrator.remove_model('user')

    migrator.remove_model('actualevent')

    migrator.remove_model('eventserie')
