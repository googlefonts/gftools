#!/usr/bin/env python3
"""
gftools packager:

Push an upstream font family to the google/fonts repository.

Usage:

# Push a family that already has a METADATA.pb file
$ gftools packager "Maven Pro" path/to/google/fonts -p

Alternatively, you can specify the METADATA.pb file directly:
$ gftools packager path/to/google/fonts/ofl/mavenpro/METADATA.pb path/to/google/fonts -p

# Push a family that doesn't have a METADATA.pb file
$ gftools packager "Maven Pro" path/to/google/fonts -p

The tool will return a path that contains a placeholder METADATA.pb file.
Modify this file by hand using your favorite text editor and then rerun
the tool using the same commands.
"""
from gftools import packager

import argparse
import logging
from rich.logging import RichHandler
import sys


log = logging.getLogger("gftools.packager")
LOG_FORMAT = "%(message)s"


def user_error_messages(type, value, traceback):
    """Print user-friendly error messages to the console when exceptions
    are raised. Intended for non-power users/type designers."""
    log.fatal(value)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "family_name",
        type=str,
        help="Name of font family or path to a METADATA.pb file",
    )
    parser.add_argument(
        "repo_path", type=str, help="Path to the google/fonts repository"
    )
    parser.add_argument(
        "-p",
        "--pr",
        help="Open a pull request on google/fonts or a forked repo",
        action="store_true",
    )
    parser.add_argument(
        "-br",
        "--base-repo",
        default="google",
        help="Repo owner to send pull request. Default is 'google'",
    )
    parser.add_argument(
        "-hr",
        "--head-repo",
        default="google",
        help="Repo owner to push branch. Default is 'google'",
    )
    parser.add_argument(
        "-l",
        "--license",
        help="licence type for new family",
        default="ofl",
        choices=("ofl", "apache", "ufl"),
    )
    parser.add_argument(
        "--latest-release",
        help="Get assets from latest upstream release",
        action="store_true",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    parser.add_argument(
        "--show-tracebacks",
        action="store_true",
        help=(
            "By default, exceptions will only print out error messages. "
            "Tracebacks won't be included since the tool is intended for "
            "type designers and not developers."
        ),
    )
    parser.add_argument("-i", "--issue-number", help="Issue number to reference in PR")
    parser.add_argument("--skip-tags", action="store_true")
    args = parser.parse_args(args)

    logging.basicConfig(
        level=args.log_level,
        format=LOG_FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler()],
    )
    if not args.show_tracebacks:
        sys.excepthook = user_error_messages
    packager.make_package(**args.__dict__)


if __name__ == "__main__":
    main()
