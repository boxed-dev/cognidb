"""`import cognidb` must not drag in the native DB connectors (they are extras).

Run in a fresh interpreter so connectors loaded by other tests don't pollute the
check. SQLite (stdlib) must work with zero extras installed.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_cognidb_does_not_import_native_connectors():
    code = (
        "import sys, cognidb\n"
        "assert 'psycopg2' not in sys.modules, 'psycopg2 imported eagerly'\n"
        "assert 'mysql.connector' not in sys.modules, 'mysql.connector imported eagerly'\n"
        "from cognidb.drivers import SQLiteDriver\n"
        "d = SQLiteDriver({'database': ':memory:'}); d.connect(); d.disconnect()\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_lazy_attribute_still_resolves_postgres_driver():
    # psycopg2 is a dev/test dep, so the lazy attribute must resolve here.
    code = (
        "import sys\n"
        "from cognidb.drivers import PostgreSQLDriver\n"
        "assert 'psycopg2' in sys.modules, 'accessing PostgreSQLDriver did not load psycopg2'\n"
        "assert PostgreSQLDriver.dialect == 'postgres'\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout
