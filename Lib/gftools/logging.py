import logging
import sys

from rich.logging import RichHandler

LOG_FORMAT = "%(message)s"


class ForeignFilter(logging.Filter):
    def filter(self, record):
        return "gftools" in record.pathname


def setup_logging(facility, args, name):
    python_minus_m = name == "__main__"
    user_mode = not python_minus_m and not getattr(args, "show_tracebacks", False)

    handler = RichHandler()

    if user_mode:
        # Even with --loglevel DEBUG, in user mode we only want to see
        # gftools-related logs.
        handler.addFilter(ForeignFilter())

    logging.basicConfig(
        level=args.log_level,
        format=LOG_FORMAT,
        datefmt="[%X]",
        handlers=[handler],
    )

    log = logging.getLogger(facility)

    def user_error_messages(_type, value, _traceback):
        """Print user-friendly error messages to the console when exceptions
        are raised. Intended for non-power users/type designers."""
        log.fatal(value)

    if user_mode:
        sys.excepthook = user_error_messages

    return log
