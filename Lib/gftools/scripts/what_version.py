"""Find which versions of gftools can successfully build a font project."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.request import urlopen

from packaging.version import Version

parser = argparse.ArgumentParser(
    description="Find which versions of gftools can successfully build a font project.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""\
examples:
  gftools what-version https://github.com/user/font-repo sources/config.yaml
  gftools what-version ./my-font-repo sources/config.yaml
  gftools what-version https://github.com/user/repo sources/config.yaml --commit abc123
""",
)
parser.add_argument("source", help="GitHub repo URL or path to local font repository")
parser.add_argument(
    "config", help="Relative path to builder config file (e.g. sources/config.yaml)"
)
parser.add_argument(
    "--commit", help="Git commit hash to checkout (only for repo URLs)"
)
parser.add_argument(
    "--workers",
    type=int,
    default=4,
    help="Max parallel version tests (default: 4)",
)
parser.add_argument(
    "--min-version",
    default="0.6.0",
    help="Minimum gftools version to test (default: 0.6.0)",
)


def get_pypi_versions(min_version="0.6.0"):
    """Fetch all available gftools versions from PyPI >= min_version."""
    url = "https://pypi.org/pypi/gftools/json"
    with urlopen(url) as resp:
        data = json.loads(resp.read().decode())

    min_ver = Version(min_version)
    versions = []
    for v in data["releases"]:
        try:
            pv = Version(v)
        except Exception:
            continue
        if pv >= min_ver and not pv.is_prerelease and not pv.is_devrelease:
            versions.append(v)

    versions.sort(key=Version)
    return versions


def clone_repo(source, dest, commit=None):
    """Clone a git repo or copy a local directory to dest."""
    is_url = source.startswith(("http://", "https://", "git@"))
    if is_url:
        cmd = ["git", "clone"]
        if not commit:
            cmd.append("--depth=1")
        cmd.extend([source, dest])
        subprocess.run(cmd, check=True, capture_output=True)
        if commit:
            subprocess.run(
                ["git", "checkout", commit],
                cwd=dest,
                check=True,
                capture_output=True,
            )
    else:
        shutil.copytree(os.path.abspath(source), dest)


def _venv_bin(venv_path):
    """Return the bin/Scripts directory inside a venv."""
    if sys.platform == "win32":
        return os.path.join(venv_path, "Scripts")
    return os.path.join(venv_path, "bin")


def test_version(version, repo_dir, config_path):
    """Test if a gftools version can build the project.

    Creates a temporary venv, installs gftools==version, runs the builder,
    and returns True if the build succeeds.
    """
    with tempfile.TemporaryDirectory() as tmp:
        venv_path = os.path.join(tmp, "venv")
        bin_dir = _venv_bin(venv_path)
        pip = os.path.join(bin_dir, "pip")
        gftools_bin = os.path.join(bin_dir, "gftools")

        try:
            subprocess.run(
                [sys.executable, "-m", "venv", venv_path],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            return False

        # Install gftools
        try:
            result = subprocess.run(
                [pip, "install", "--no-cache-dir", f"gftools=={version}"],
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return False
        if result.returncode != 0:
            return False

        # Run builder
        try:
            result = subprocess.run(
                [gftools_bin, "builder", config_path],
                cwd=repo_dir,
                capture_output=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            return False

        return result.returncode == 0


def find_working_versions(versions, repo_dir, config_path, max_workers=4):
    """Binary search for working gftools versions.

    On success: search both lower and upper halves (in parallel).
    On failure: search upper half only.
    """
    working = []
    lock = threading.Lock()
    semaphore = threading.Semaphore(max_workers)

    def search(start, end):
        if start > end:
            return

        mid = (start + end) // 2
        version = versions[mid]

        print(f"Testing gftools=={version} ...")

        with semaphore:
            success = test_version(version, repo_dir, config_path)

        if success:
            print(f"  gftools=={version}  PASS")
            with lock:
                working.append(version)
            # Search both halves in parallel
            t_lo = threading.Thread(target=search, args=(start, mid - 1))
            t_hi = threading.Thread(target=search, args=(mid + 1, end))
            t_lo.start()
            t_hi.start()
            t_lo.join()
            t_hi.join()
        else:
            print(f"  gftools=={version}  FAIL")
            # Only search upper half
            search(mid + 1, end)

    search(0, len(versions) - 1)

    working.sort(key=Version)
    return working


def main(args=None):
    args = parser.parse_args(args)

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = os.path.join(tmp_dir, "repo")

        print(f"Preparing repository from {args.source} ...")
        clone_repo(args.source, repo_dir, commit=args.commit)

        config_full = os.path.join(repo_dir, args.config)
        if not os.path.exists(config_full):
            sys.exit(f"Error: config file not found: {args.config}")

        print("Fetching available gftools versions from PyPI ...")
        versions = get_pypi_versions(args.min_version)
        print(f"Found {len(versions)} versions (>= {args.min_version})")

        if not versions:
            sys.exit("No versions found to test.")

        print(
            f"Starting binary search with up to {args.workers} parallel tests ...\n"
        )
        working = find_working_versions(
            versions, repo_dir, args.config, max_workers=args.workers
        )

        print()
        if working:
            print(f"Versions that can build this project ({len(working)}):")
            for v in working:
                print(f"  gftools=={v}")
        else:
            print("No working versions found.")


if __name__ == "__main__":
    main()
