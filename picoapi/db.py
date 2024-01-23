import os

import btree


class BTreeDatabase:
    def __init__(self, **kwargs):
        """
        Create a new BTreeDatabase engine instance.

        Args:
            path (str): The path to the database file.
        """

        self.path = kwargs.get("path")
        self._handle = None
        self._db = None

    def db_open(self):
        """
        Open the database file and return a database provider.
        """
        self._handle = open(self.path, "br+", )
        self._db = btree.open(self._handle)

    def db_close(self):
        """
        Close and save the database file.
        """
        self._db.close()
        self._handle.close()

    def get(self, key, default=None):
        """
        Get a value from the database.

        Args:
            key (bytes or str): The key to get.
            default: The default value to return if the key does not exist.
        """
        try:
            return self._db[key]
        except KeyError:
            return default

    def set(self, key, value):
        """
        Set a value in the database.

        Args:
            key (bytes or str): The key to set.
            value: The value to set.
        """
        if not isinstance(key, (bytes, str)):
            raise ValueError("key must be bytes or str for btree database")

        self._db[key] = value

    def delete(self, key):
        """
        Delete a value from the database.

        Args:
            key (bytes or str): The key to delete.
        """
        del self._db[key]

    def keys(self):
        """
        Get all keys in the database.

        Returns:
            list: A list of keys.
        """
        return self._db.keys()

    def values(self):
        """
        Get all values in the database.

        Returns:
            list: A list of values.
        """
        return self._db.values()

    def items(self):
        """
        Get all items in the database.

        Returns:
            list: A list of items.
        """
        return self._db.items()


class Database:
    def __init__(self, engine, path):
        """
        Create a new database connection instance.

        Args:
            path (str): The path to the database file.
        """
        self.engine = engine
        self.path = path
        self._handle = None
        self._db = None

    def __enter__(self):
        """
        Open the database file and return a database provider.

        Returns:
            BTreeDatabase: A database engine object instance.
        """
        return self.engine(self.path).db_open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close the database file.

        Args:
            exc_type: The exception type.
            exc_val: The exception value.
            exc_tb: The exception traceback.
        """
        self.engine(self.path).db_close()