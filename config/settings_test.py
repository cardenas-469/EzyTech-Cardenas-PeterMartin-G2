"""Test settings.

The development/production database is PostgreSQL (Supabase). Supabase's
connection pooler does not allow the CREATE DATABASE statement that Django's
test runner needs, so tests run against an in-memory SQLite database.
Production data access still uses PostgreSQL through config.settings.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
