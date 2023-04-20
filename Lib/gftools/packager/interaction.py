import os
import typing
from collections import OrderedDict


def get_editor_command():
    # # there's some advice to chose an editor to open and how to set a default
    # https://stackoverflow.com/questions/10725238/opening-default-text-editor-in-bash
    # I like chosing VISUAL over EDITOR falling back to vi, where on my
    # system actually vi equals vim:
    # ${VISUAL:-${EDITOR:-vi}}
    return os.environ.get("VISUAL", os.environ.get("EDITOR", "vi"))


def user_input(
    question: str,
    options: "OrderedDict[str, str]",
    default: typing.Union[str, None] = None,
    yes: typing.Union[bool, None] = None,
    quiet: bool = False,
):
    """
    Returns one of the keys of the *options* dict.

    In interactive mode (if *yes* is not True, see below) use the
    *input()* function to ask the user a *question* and present the user
    with the possible answers in *options*. Where the keys in *options*
    are the actual options to enter and the values are the descriptions
    or labels.

    default: if *yes* is a bool this should be an option that does
    not require user interaction. That way we can have an all -y/--no-confirm
    flag will always choose the default.

    yes: don't ask the user and use the default. If the value is a boolean
    *default* must be set, because we expect the boolean comes from the
    -y/--no-confirm flag and the programmers intent is to make this dialogue
    usable with that flag. If the value is None, we don't check if default is
    set. The boolean False versus None differentiation is intended as a self
    check to raise awareness of how to use this function.

    quiet: if *yes* is true don't print the question to stdout.
    """
    if default is not None and default not in options:
        # UX: all possible choices must be explicit.
        raise Exception(
            f"default is f{default} but must be one of: "
            f'{", ".join(options.keys())}.'
        )
    if yes is not None and default is None:
        # This is a programming error see the __doc__ string above.
        raise Exception("IF yes is is a boolean, default can't be None.")

    options_items = [
        f'{"["+k+"]" if default==k else k}={v}' for k, v in options.items()
    ]
    question = f'{question}\nYour options {",".join(options_items)}:'

    if yes:
        if not quiet:
            # Don't ask, but print to document the default decision.
            print(question, default)
        return default

    while True:
        answer = input(question).strip()
        if answer == "" and default is not None:
            return default
        if answer in options:
            return answer
        # else will ask again
