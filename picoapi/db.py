import os

import btree


class BTreeDatabaseProvider:
    def __init__(self, db):
        self.db = db

    def get(self, key, default=None):
        try:
            return self.db[key]
        except KeyError:
            return default

    def set(self, key, value):
        if not isinstance(key, (bytes, str)):
            raise ValueError("key must be bytes or str for btree database")

        self.db[key] = value

    def delete(self, key):
        del self.db[key]

    def keys(self):
        return self.db.keys()

    def values(self):
        return self.db.values()

    def items(self):
        return self.db.items()


class SimpleDB:
    def __init__(self, path):
        """
        Create a new SimpleDB instance.

        Args:
            path (str): The path to the database file.
        """
        self.path = path
        self._handle = None
        self._db = None

    def __enter__(self):
        """
        Open the database file and return a database provider.

        Returns:
            BTreeDatabaseProvider: A database provider.
        """
        self._handle = open(self.path, "br+")
        self._db = btree.open(self._handle)
        return BTreeDatabaseProvider(self._db)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._db.close()
        self._handle.close()
