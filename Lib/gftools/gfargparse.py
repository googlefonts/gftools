import argparse as dflt_argparse
from gftools.gflogging import setup_logging


class GFArgumentParser(dflt_argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--log-level",
            choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
            default="INFO",
        )

        self.add_argument(
            "--show-tracebacks", "-st",
            action="store_true",
            help=(
                "By default, exceptions will only print out error messages. "
                "Tracebacks won't be included since the tool is intended for "
                "type designers and not developers."
            ),
        )

    def parse_args(self, args=None, namespace=None):
        args, argv = self.parse_known_args(args, namespace)
        if argv:
            msg = ('unrecognized arguments: %s')
            self.error(msg % ' '.join(argv))
        import pdb; pdb.set_trace()
        setup_logging("gftools.packager", args, "packager")
        return args
