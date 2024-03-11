#!/usr/bin/env python3
from pprint import pprint
from gftools.packager import load_metadata, make_package, no_source_metadata
import argparse
import os
from pathlib import Path
import logging
from rich.logging import RichHandler

log = logging.getLogger("gftools.packager")
LOG_FORMAT = "%(message)s"


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Path to the google/fonts repository")
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    args = parser.parse_args(args)

    logging.basicConfig(
        level=args.log_level,
        format=LOG_FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler()],
    )

    failed = []
    for dirpath, _, filenames in os.walk(args.repo):
        for filename in filenames:
            if filename != "METADATA.pb":
                continue
            family_path = Path(dirpath)
            meta_path = family_path / "METADATA.pb"
            metadata = load_metadata(meta_path)
            if no_source_metadata(metadata):
                continue
            try:
                make_package(
                    args.repo,
                    str(family_path / "METADATA.pb"),
                    pr=True,
                    base_repo="m4rc1e",
                    head_repo="m4rc1e",
                )
            except Exception as e:
                print(f"Failed to make package for {family_path}: {e}")
                failed.append(family_path)
            log.info("---")

    print(f"Failed to make packages for {len(failed)} families")
    pprint(failed)


if __name__ == "__main__":
    main()
