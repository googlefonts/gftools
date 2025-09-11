import argparse
from pathlib import Path
from gftools.article import fix_article
from gftools.logging import setup_logging


def main(args=None):
    parser = argparse.ArgumentParser(description="Fix media in article directories.")
    parser.add_argument(
        "family_fp",
        type=Path,
        help="Path to the article directory to fix.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )
    out_group = parser.add_mutually_exclusive_group(required=True)
    out_group.add_argument(
        "-o",
        "--out",
        type=Path,
        help="Output directory for updated article dir",
    )
    out_group.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Do not write any files, just print what would be done.",
    )
    out_group.add_argument(
        "--inplace", action="store_true", help="Update the article dir in place."
    )
    args = parser.parse_args(args)
    setup_logging("gftools.packager", args, __name__)
    article_fp = args.family_fp / "article"
    if not article_fp.exists():
        raise FileNotFoundError(f"Article directory not found: {article_fp}")

    fix_article(
        args.family_fp / "article",
        out=args.out,
        inplace=args.inplace,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
