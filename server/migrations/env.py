"""Alembic: миграции схемы SmartQueue. Адрес базы — переменная DATABASE_URL."""

import os

from alembic import context
from sqlalchemy import create_engine

url = os.environ["DATABASE_URL"]


def run():
    if context.is_offline_mode():
        context.configure(url=url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    with create_engine(url).connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()


run()
