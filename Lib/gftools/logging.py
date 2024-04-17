import logging
import sys

from rich.logging import RichHandler

LOG_FORMAT = "%(message)s"


def setup_logging(facility, args, name):
    logging.basicConfig(
        level=args.log_level,
        format=LOG_FORMAT,
        datefmt="[%X]",
        handlers=[RichHandler()],
    )

    log = logging.getLogger(facility)

    def user_error_messages(_type, value, _traceback):
        """Print user-friendly error messages to the console when exceptions
        are raised. Intended for non-power users/type designers."""
        log.fatal(value)

    python_minus_m = name == "__main__"
    if not python_minus_m and not args.show_tracebacks:
        sys.excepthook = user_error_messages

    return log
