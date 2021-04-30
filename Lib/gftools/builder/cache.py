from fontTools.designspaceLib import DesignSpaceDocument
from fontTools.feaLib.lexer import Lexer
from glyphsLib import GSFont
import os
import sqlite3
from collections import defaultdict
from pkg_resources import resource_filename
from gftools.utils import md5_hash
from pkg_resources import working_set
import shutil
import yaml
import json
from pathlib import Path
import hashlib
import tarfile
import io


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

    def find_linked_files(self, files):
        """Get referenced source files"""
        ufos = []
        fea = []
        return files

    def add_files(self, files):
        # TODO get ufos from designspaces and linked fea files
        files = self.find_linked_files(files)
        # Remove previously cached files
        for f in files:
            if os.path.isfile(f):
                suffix = os.path.dirname(f)
            else:
                suffix = f
            self.cur.execute("DELETE FROM file_cache WHERE file LIKE '%%%s%%'" % suffix)

        file_hashes = self._hash_files(files)

        for filepath, filehash in file_hashes.items():
            self.cur.execute(
                "INSERT INTO file_cache VALUES (?,?)", (filepath, filehash)
            )
        self.con.commit()
        return files

    def changed_files(self, files):
        previous_hashes = {}
        for f in files:
            if os.path.isfile(f):
                suffix = os.path.dirname(f)
            else:
                suffix = f
            self.cur.execute("SELECT * FROM file_cache WHERE file LIKE '%%%s%%'" % suffix)
            previous_hashes = {k: v for k, v in self.cur.fetchall()}

        results = {}

        missing = set(previous_hashes) - set(files)
        if missing:
            results['missing'] = sorted(list(missing))

        new = set(files) - set(previous_hashes)
        if new:
            results['new'] = sorted(list(new))

        matching_files = set(files) & set(previous_hashes)
        file_hashes = self._hash_files(matching_files)
        for key in matching_files:
            if file_hashes[key] != previous_hashes[key]:
                if not "modified" in results:
                    results['modified'] = []
                results['modified'].append(key)
        if "modified" in results:
            results['modified'] = sorted(results['modified'])
        return results

    def _get_source_files(self, files):
        source_files = []
        for f in files:
            # Get ufo paths from a designspace
            if f.endswith(".designspace"):
                ds = DesignSpaceDocument()
                ds.read(f)
                for ufo in ds.sources:
                    source_files.append(ufo.path)
            source_files.append(f)

        ufo_files = []
        for f in source_files:
            # Get individual files in a ufo
            if f.endswith(".ufo"):
                ufo_path = Path(f)
                sub_files = list(ufo_path.rglob("*"))
                # find linked fea files
                for s_f in sub_files:
                    if s_f.suffix == ".fea":
                        ufo_files += self._get_fea_files(s_f, os.path.dirname(f))
                    if s_f.is_file():
                        ufo_files.append(str(s_f))

        glyphs_files = []
        for f in source_files:
            if f.endswith(".glyphs"):
                font = GSFont(f)
        return [str(f) for f in source_files + ufo_files if not str(f).endswith(".ufo")]

    def _get_fea_files(self, fea, d_):
        """Use stack based Depth First Search in order to find sibling .fea
        files which are linked using the include .fea statement.

        http://adobe-type-tools.github.io/afdko/OpenTypeFeatureFileSpecification.html#3
        """
        stack = [fea]
        res, seen = [], set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            res.append(n)
            l = Lexer(open(n).read(), n)
            stack += [os.path.join(d_, fp) for t, fp, _, in l if t == "FILENAME"]
        return res

    def _hash_files(self, files):
        res = {}
        for f in files:
            if os.path.isdir(f):
                res[f] = self.md5_hash_dir(f)
            elif os.path.isfile(f):
                res[f] = md5_hash(f)
            else:
                raise IOError(f"{f} is not a file or directory")
        return res

    @staticmethod
    def md5_hash_dir(fp):
        # Calculating the hash for every file using os.walk is slow. Since
        # the hashes don't need to be portable to other machines, we can
        # simply zip the directory then calculate the checksum of the zip
        # file.
        r = io.BytesIO()
        with tarfile.open(fileobj=r, mode='w') as tar:
            tar.add(fp, recursive=True)
        hash_ = hashlib.md5()
        hash_.update(r.getvalue())
        return hash_.hexdigest()

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
        if not fp:
            return None
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
        if not fp:
            return None
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
