"""Public package must import cleanly."""


def test_import_cognidb_api():
    from cognidb import CogniDB, create_cognidb, __version__

    assert callable(create_cognidb)
    assert CogniDB is not None
    assert __version__


def test_import_drivers():
    from cognidb.drivers import MySQLDriver, PostgreSQLDriver

    assert MySQLDriver is not None
    assert PostgreSQLDriver is not None


def test_import_security():
    from cognidb.security import QuerySecurityValidator, InputSanitizer, AccessController

    assert QuerySecurityValidator is not None
    assert InputSanitizer is not None
    assert AccessController is not None
