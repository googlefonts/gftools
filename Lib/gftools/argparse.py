from argparse import ArgumentParser


class GFArgumentParser(ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--show-tracebacks", action="store_true", help="Show tracebacks"
        )
