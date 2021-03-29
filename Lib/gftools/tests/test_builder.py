from gftools.builder.cache import Cache
import pytest
import tempfile
import os


def test_caching_files():

    with tempfile.NamedTemporaryFile(suffix=".db") as db, \
         tempfile.NamedTemporaryFile() as f1, \
         tempfile.NamedTemporaryFile() as f2:

        cache = Cache(db_path=db.name)

        # Test empty files
        files = [f1.name, f2.name]
        cache.add_files(files)
        assert cache.changed_files(files) == []

        # Test updating just a single file
        f1.write(b"foobar")
        f1.seek(0)
        assert len(cache.changed_files(files)) == 1
        assert cache.changed_files(files)[0] == f1.name

        # Test updating both files
        f2.write(b"foobar2")
        f2.seek(0)
        assert len(cache.changed_files(files)) == 2
        assert set(files) == set(cache.changed_files(files))

        # Readd the modified files and retest
        cache.add_files(files)
        assert cache.changed_files(files) == []
        cache.con.close()


def test_caching_config_file():

    with tempfile.NamedTemporaryFile(suffix=".db") as db, \
        tempfile.NamedTemporaryFile() as f1:

        # Test adding a new config and testing the same config gainst it
        cache = Cache(db_path=db.name)
        f1.write(b"familyName: Foobar\nincludeSourceFixes: true")
        f1.seek(0)

        cache.add_config(f1.name)
        assert cache.changed_config(f1.name) == False

        # Update the config file and retest it
        f1.write(b"familyName: Barfoo\nincludeSourceFixes: false")
        f1.seek(0)
        assert cache.changed_config(f1.name) == True

        # Readd the modified config and retest
        cache.add_config(f1.name)
        assert cache.changed_config(f1.name) == False


def test_caching_directory():

    with tempfile.NamedTemporaryFile(suffix=".db") as db, \
        tempfile.TemporaryDirectory() as test_dir:

        cache = Cache(db_path=db.name)

        # Test an empty dir
        cache.add_directory(test_dir)
        assert cache.changed_directory(test_dir) == {}

        # Test on a new file
        f1 = os.path.join(test_dir, "f1.txt")
        with open(f1, "w") as doc:
            doc.write("Hello world")
        assert cache.changed_directory(test_dir) == {"new": [f1]}

        # Add another file
        f2 = os.path.join(test_dir, "f2.txt")
        with open(f2, "w") as doc:
            doc.write("Hello world")
        assert cache.changed_directory(test_dir) == {"new": [f1, f2]}

        # update cache
        cache.add_directory(test_dir)

        # delete a cached file
        os.remove(f2)
        assert cache.changed_directory(test_dir) == {"missing": [f2]}

        # modify a cached file
        cache.add_directory(test_dir)
        with open(f1, "w") as doc:
            doc.write("Hello again")
        assert cache.changed_directory(test_dir) == {"modified": [f1]}
