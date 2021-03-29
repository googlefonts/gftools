import os
import sqlite3
from collections import defaultdict
from pkg_resources import resource_filename
from gftools.utils import md5_hash
from pkg_resources import working_set
import shutil
import yaml
import json


class Cache(object):
    def __init__(self, db_path=resource_filename("gftools", "builder_cache.db")):
        """A simple cache for the gftools builder.

        The aim of this cache is to check whether fontmake needs to regenerate
        font binaries. This needs to happen if the source files have changed,
        the python dependencies have been updated, the config file has been
        modified (excludes changes made to font instances and stat changes) or
        if the font binaries have been moved/deleted.

        The cache doesn't store the contents of files or directories. It only
        stores the file's path and an md5 checksum.

        Args:
            db_path: path to create db. By default it is saved to the gftools
            dependency dir
        """
        self.db_path = db_path
        self.con = sqlite3.connect(self.db_path)
        self.cur = self.con.cursor()
        self._init_db()

    def _init_db(self):
        self.cur.execute("CREATE TABLE IF NOT EXISTS file_cache (file, md5)")
        self.cur.execute(
            "CREATE TABLE IF NOT EXISTS dependency_cache (python_path, md5)"
        )
        self.cur.execute("CREATE TABLE IF NOT EXISTS config_cache (path, data)")
        self.con.commit()

    def delete_all_records(self):
        """Delete all database records."""
        self.cur.execute("DROP TABLE file_cache")
        self.cur.execute("DROP TABLE dependency_cache")
        self.cur.execute("DROP TABLE config_cache")
        self._init_db()

    def add_files(self, files):
        file_hashes = self._hash_files(files)
        for filepath, filehash in file_hashes.items():
            self.cur.execute("SELECT * from file_cache WHERE file=?", (filepath,))
            if not self.cur.fetchone():
                self.cur.execute(
                    "INSERT INTO file_cache VALUES (?,?)", (filepath, filehash)
                )
            else:
                self.cur.execute(
                    "UPDATE file_cache SET md5=? WHERE file=?", (filehash, filepath)
                )
        self.con.commit()
        return files

    def changed_files(self, files):
        source_files = []
        for f in files:
            # Get ufo paths from a designspace
            if f.endswith(".designspace"):
                ds = designspaceLib()
                ds.read(f)
                for ufo in ds.sources:
                    source_files.append(ufo)
            source_files.append(f)

        changed = []
        file_hashes = self._hash_files(source_files)
        for filepath, filehash in file_hashes.items():
            self.cur.execute("SELECT * FROM file_cache WHERE file=?", (filepath,))
            previous_hash = self.cur.fetchone()
            if not previous_hash:
                changed.append(filepath)
                continue
            _, previous_filehash = previous_hash
            if previous_filehash != filehash:
                changed.append(filepath)
        return changed

    def _hash_files(self, files):
        return {f: md5_hash(f) for f in files}

    def add_directory(self, fp):
        # Remove any existing records which belong to the fp
        self.cur.execute("DELETE FROM file_cache WHERE file LIKE '%%%s%%'" % fp)
        files = [os.path.join(fp, f) for f in os.listdir(fp) if f != ".DS_Store"]
        return self.add_files(files)

    def changed_directory(self, fp):
        files = [os.path.join(fp, f) for f in os.listdir(fp) if f != ".DS_Store"]
        files = self._hash_files(files)
        self.cur.execute("SELECT * FROM file_cache WHERE file LIKE '%%%s%%'" % fp)
        previous_files = {k: v for k, v in self.cur.fetchall()}
        diff = defaultdict(list)
        for filepath, file_hash in files.items():
            if filepath not in previous_files:
                diff["new"].append(filepath)
                continue

            if files[filepath] != previous_files[filepath]:
                diff["modified"].append(filepath)

        for filepath, file_hash in previous_files.items():
            if filepath not in files:
                diff["missing"].append(filepath)
                continue

        return dict(diff)

    def add_dependencies(self):
        python_path = shutil.which("python")
        dependencies = self._get_dependencies()
        self.cur.execute(
            "SELECT * from dependency_cache WHERE python_path=?", (python_path,)
        )
        if not self.cur.fetchone():
            self.cur.execute(
                "INSERT INTO dependency_cache VALUES (?,?)", (python_path, dependencies)
            )
        else:
            self.cur.execute(
                "UPDATE dependency_cache SET md5=? WHERE python_path=?",
                (dependencies, python_path),
            )
        self.con.commit()
        return dependencies

    def changed_dependencies(self):
        python_path = shutil.which("python")
        dependencies = self._get_dependencies()
        self.cur.execute(
            "SELECT * FROM dependency_cache WHERE python_path=?", (python_path,)
        )
        previous_dependencies = self.cur.fetchone()
        if not previous_dependencies:
            return True
        _, previous_dependencies = previous_dependencies
        if previous_dependencies != dependencies:
            return True
        return False

    def _get_dependencies(self):
        return ",".join(str(s) for s in sorted(working_set))

    def add_config(self, fp):
        config_data = json.dumps(self._load_config(fp))
        self.cur.execute("SELECT * FROM config_cache WHERE path=?", (fp,))
        if not self.cur.fetchone():
            self.cur.execute("INSERT INTO config_cache VALUES (?,?)", (fp, config_data))
        else:
            self.cur.execute(
                "UPDATE config_cache SET data=? WHERE path=?", (config_data, fp)
            )
        self.con.commit()
        return config_data

    def changed_config(self, fp):
        config_data = self._load_config(fp)
        self.cur.execute("SELECT * FROM config_cache WHERE path=?", (fp,))
        previous_config = self.cur.fetchone()
        if not previous_config:
            return True
        previous_config_data = json.loads(previous_config[-1])
        if previous_config_data != config_data:
            return True
        return False

    def _load_config(self, fp):
        with open(fp) as yaml_data:
            data = yaml.load(yaml_data, Loader=yaml.FullLoader)
            # Remove stat and instance data since we want users to
            # be able to edit these since they don't rely on fontmake
            if "stat" in data:
                data.pop("stat")
            if "instances" in data:
                data.pop("instances")
        return data

    def add_project(self, project):
        self.add_files(project.config["sources"])
        self.add_config(project.configfile)
        self.add_dependencies()

    def changed_project(self, project):
        return any(
            [
                self.changed_files(project.config["sources"]),
                self.changed_config(project.configfile),
                self.changed_dependencies(),
            ]
        )

    def close(self):
        self.con.close()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
