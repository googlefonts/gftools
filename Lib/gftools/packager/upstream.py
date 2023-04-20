# Things dealing with upstream.yaml files

from pkg_resources import resource_filename
from collections import OrderedDict
from tempfile import mkstemp
import sys
import subprocess
import os
import typing
from typing import TYPE_CHECKING

from strictyaml import (  # type: ignore
    Map,
    UniqueSeq,
    MapPattern,
    Enum,
    Str,
    EmptyNone,
    EmptyDict,
    Optional,
    YAML,
    YAMLValidationError,
    dirty_load,
    as_document,
)
from google.protobuf import text_format  # type: ignore


if TYPE_CHECKING:
    fonts_pb2: typing.Any
else:
    import gftools.fonts_public_pb2 as fonts_pb2

from gftools.github import GitHubClient
from gftools.packager.constants import (
    CATEGORIES,
    CLEARLINE,
    GITHUB_GRAPHQL_GET_FAMILY_ENTRY,
    LICENSE_DIRS,
    TOLEFT,
)
from gftools.packager import _file_or_family_is_file  # For now
from gftools.packager import _family_name_normal  # For now
from gftools.packager.exceptions import UserAbortError, ProgramAbortError
from gftools.packager.interaction import user_input, get_editor_command


with open(resource_filename("gftools", "template.upstream.yaml")) as f:
    upstream_yaml_template = f.read()
    # string.format fails if we use other instances of {variables}
    # without adding them to the call to format (KeyError).
    upstream_yaml_template = upstream_yaml_template.replace(
        "{CATEGORIES}", ", ".join(CATEGORIES)
    )

# Eventually we need all these keys to make an update, so this
# can't have Optional/Empty entries, unless that's really optional for
# the process.
upstream_yaml_schema = Map(
    {
        "name": Str(),
        "repository_url": Str(),  # TODO: custom validation please
        "branch": Str(),
        Optional("archive", default=""): EmptyNone() | Str(),
        "category": UniqueSeq(Enum(CATEGORIES)),
        "designer": Str(),
        Optional("build", default=""): EmptyNone() | Str(),
        # allowing EmptyDict here, even though we need files in here,
        # but we will catch missing files later in the process.
        # When we have repository_url and branch we can add a editor based
        # dialog that suggests all files present in the repo (delete lines of
        # files you don't want to include).
        "files": EmptyDict()
        | MapPattern(Str(), Str()),  # Mappings with arbitrary key names
    }
)

# Since upstream_yaml_template is incomplete, it can't be parsed with
# the complete upstream_yaml_schema. Here's a more forgiving schema for
# the template and for initializing with a stripped upstream_conf.
upstream_yaml_template_schema = Map(
    {
        Optional("name", default=""): EmptyNone() | Str(),
        Optional("repository_url", default=""): EmptyNone()
        | Str(),  # TODO: custom validation please
        "branch": EmptyNone() | Str(),
        Optional("archive", default=""): EmptyNone() | Str(),
        Optional("category", default=None): EmptyNone() | UniqueSeq(Enum(CATEGORIES)),
        Optional("designer", default=""): EmptyNone() | Str(),
        Optional("build", default=""): EmptyNone() | Str(),
        "files": EmptyDict() | MapPattern(Str(), Str()),
    }
)

upstream_yaml_stripped_schema = Map(
    {  # TODO: custom validation please
        # Only optional until it can be in METADATA.pb
        Optional("repository_url", default=""): Str(),
        "branch": EmptyNone() | Str(),
        Optional("archive", default=""): EmptyNone() | Str(),
        Optional("build", default=""): EmptyNone() | Str(),
        "files": EmptyDict() | MapPattern(Str(), Str()),
    }
)


def format_upstream_yaml(upstream_yaml: YAML, compact: bool = True):
    # removes comments to make it more compact to read
    if compact:
        description = "upstream configuration (no comments, normalized)"
        content = as_document(upstream_yaml.data, upstream_yaml_schema).as_yaml()
    else:
        description = "upstream configuration"
        content = upstream_yaml.as_yaml()
    len_top_bars = (58 - len(description)) // 2
    top = f'{"-"*len_top_bars} {description} {"-"*len_top_bars}'
    return f"{top}\n" f"{content}" f'{"-"*len(top)}'


def _repl_upstream_conf(
    initial_upstream_conf: str,
    yes: bool = False,
    quiet: bool = False,
    use_template_schema=False,
):
    if yes:
        raise UserAbortError()
    # repl means "read-eval-print loop"
    editor = get_editor_command()

    # it would be nice to have a location where the file can be inspected
    # after this program ends, similar to swp files of vim or how git stores
    # such files. However, that should maybe be in the upstream repository
    # rather than in the current working directory. Since I'm undecided
    # I simply go with a temp file
    _tempfilefd, upstream_yaml_file_name = mkstemp(suffix=".yaml", prefix="upstream")
    try:
        # Unlike TemporaryFile(), the user of mkstemp() is responsible for
        # deleting the temporary file when done with it.
        os.close(_tempfilefd)
        print(f"temp file name is {upstream_yaml_file_name}")

        last_good_conf = None
        edit_challenge = initial_upstream_conf

        while True:
            # truncates the file on open
            with open(upstream_yaml_file_name, "w") as upstream_yaml_file:
                upstream_yaml_file.write(edit_challenge)
            # open it in an editor
            # NOTE the carriage return, this line will be removed again.
            # not sure if this should go to stdout or stderr
            print(
                "hint: Waiting for your editor to close the file ...",
                end="",
                flush=True,
                file=sys.stderr,
            )
            subprocess.run([editor, upstream_yaml_file_name])
            print(CLEARLINE + TOLEFT, end="", flush=True, file=sys.stderr)

            # read the file
            with open(upstream_yaml_file_name, "r") as upstream_yaml_file:
                updated_upstream_conf = upstream_yaml_file.read()

            # parse the file
            try:
                yaml_schema = (
                    upstream_yaml_schema
                    if not use_template_schema
                    else upstream_yaml_template_schema
                )
                last_good_conf = dirty_load(
                    updated_upstream_conf, yaml_schema, allow_flow_style=True
                )
            except Exception as e:
                answer = user_input(
                    f"The configuration did not parse ({type(e).__name__}):\n\n" f"{e}",
                    OrderedDict(
                        f="fix last edit",
                        r="retry last edit",
                        s="start all over",
                        q="quit program",
                    ),
                    # the default should always be an option that does
                    # not require user interaction. That way we can
                    # have an all -y/--no-confirm flag that always
                    # chooses the default.
                    default="q",
                    yes=yes,
                    quiet=quiet,
                )
                if answer == "f":
                    edit_challenge = updated_upstream_conf
                elif answer == "r":
                    # edit_challenge = edit_challenge
                    pass
                elif answer == "s":
                    edit_challenge = initial_upstream_conf
                else:  # anser == 'q':
                    raise UserAbortError()
                continue

            return last_good_conf
            # This was thought as an extra check for the user, but I think it's
            # rather anoying than helpful. Note, the user just edited and
            # it parsed successfully.
            # # Ask the user if this looks good.
            # answer = user_input('Use this upstream configuration?\n'
            #       f'{format_upstream_yaml(last_good_conf)}',
            #       OrderedDict(y='yes',
            #                   e='edit again',
            #                   s='start all over',
            #                   q='quit program'),
            #       default='y', yes=yes, quiet=quiet)
            # if answer == 'y':
            #   return last_good_conf
            # elif answer == 'e':
            #   edit_challenge = last_good_conf.as_yaml()
            # elif answer == 's':
            #   edit_challenge = initial_upstream_conf
            # else: # answer == 'q':
            #   raise UserAbortError()
    finally:
        os.unlink(upstream_yaml_file_name)


def _load_upstream(
    upstream_yaml_text: str,
    use_template_schema: bool = False,
) -> typing.Tuple[bool, YAML]:
    try:
        yaml_schema = (
            upstream_yaml_schema
            if not use_template_schema
            else upstream_yaml_template_schema
        )
        return False, dirty_load(upstream_yaml_text, yaml_schema, allow_flow_style=True)
    except YAMLValidationError as err:
        print("The configuration has schema errors:\n\n" f"{err}")
        raise ProgramAbortError()


def _upstream_conf_from_file(
    filename: str,
    yes: bool = False,
    quiet: bool = False,
    use_template_schema: bool = False,
) -> YAML:
    """If this parses there will be no repl, the user can edit
    the file directly on disk.
    If it doesn't parse, there's a chance to edit until the yaml parses
    and to change the result back to disk.
    """
    with open(filename, "r+") as upstream_yaml_file:
        upstream_yaml_text = upstream_yaml_file.read()
        edited, upstream_conf_yaml = _load_upstream(
            upstream_yaml_text,
            use_template_schema=use_template_schema,
        )
        # "edited" is only true when upstream_yaml_text did not parse and
        # was then edited successfully.
        if edited:
            answer = user_input(
                f"Save changed file {filename}?",
                OrderedDict(y="yes", n="no"),
                default="y",
                yes=yes,
                quiet=quiet,
            )
            if answer == "y":
                upstream_yaml_file.seek(0)
                upstream_yaml_file.truncate()
                upstream_yaml_file.write(upstream_conf_yaml.as_yaml())
    return upstream_conf_yaml


def _upstream_conf_from_scratch(
    family_name: typing.Union[str, None] = None,
    yes: bool = False,
    quiet: bool = False,
    use_template_schema: bool = False,
) -> YAML:

    upstream_conf_yaml = dirty_load(
        upstream_yaml_template, upstream_yaml_template_schema, allow_flow_style=True
    )
    if family_name is not None:
        upstream_conf_yaml["name"] = family_name

    if use_template_schema and yes:  # for -u/--upstream-yaml
        return upstream_conf_yaml

    template = upstream_conf_yaml.as_yaml()
    return _repl_upstream_conf(
        template, yes=yes, quiet=quiet, use_template_schema=use_template_schema
    )


def _upstream_conf_from_yaml_metadata(
    upstream_yaml_text: typing.Union[str, None],
    metadata_text: typing.Union[str, None],
    yes: bool = False,
    quiet: bool = False,
    use_template_schema: bool = False,
) -> YAML:
    """Make a package when the family is in the google/fonts repo.
    Uses data preferred from upstream.yaml, if already present, and fills
    the gaps with data from METADATA.pb. This is to enable the removal of
    redundant data from upstream.yaml when it is in METADATA.pb, while also
    keeping upstream.yaml as the source of truth when in doubt.

    Eventually the common update path.
    """
    upstream_conf = {}
    if metadata_text is not None:
        metadata = fonts_pb2.FamilyProto()
        text_format.Parse(metadata_text, metadata)
        # existing repo, no upstream conf:
        # from METADATA.pb we use:
        #       designer, category, name
        # we won't get **yet**:
        #       source.repository_url
        # we still need the new stuff:
        #       branch, files
        upstream_conf.update(
            {
                "designer": metadata.designer or None,
                "category": list(metadata.category) or None,
                "name": metadata.name or None,
                # we won't get this just now in most cases!
                "repository_url": metadata.source.repository_url or None,
            }
        )
    if upstream_yaml_text is not None:
        # Only drop into REPL mode if can't parse and validate,
        # and use use_template_schema, because this is not the real deal
        # yet and we can be very forgiving.
        _, upstream_conf_yaml = _load_upstream(
            upstream_yaml_text, use_template_schema=True
        )

        # remove None values:
        upstream_conf_yaml_data = {
            k: v for k, v in upstream_conf_yaml.data.items() if v is not None
        }
        # Override keys set by METADATA.pb before, if there's overlap.
        upstream_conf.update(upstream_conf_yaml_data)

    upstream_conf_yaml = dirty_load(
        upstream_yaml_template, upstream_yaml_template_schema, allow_flow_style=True
    )
    for k, v in upstream_conf.items():
        if v is None:
            continue
        upstream_conf_yaml[k] = v

    upstream_yaml_text = upstream_conf_yaml.as_yaml()
    assert upstream_yaml_text is not None

    _, upstream_conf_yaml = _load_upstream(
        upstream_yaml_text,
        use_template_schema=use_template_schema,
    )
    return upstream_conf_yaml


def get_upstream_info(
    file_or_family: str,
    is_file: bool,
    yes: bool,
    quiet: bool,
    require_license_dir: bool = True,
    use_template_schema: bool = False,
) -> typing.Tuple[YAML, typing.Union[str, None], dict]:
    # the first task is to acquire an upstream_conf, the license dir and
    # if present the available files for the family in the google/fonts repo.
    license_dir: typing.Union[str, None] = None
    upstream_conf_yaml = None
    gf_dir_content: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

    if not is_file:
        family_name = file_or_family
    else:
        # load a upstream.yaml from disk
        upstream_conf_yaml = _upstream_conf_from_file(
            file_or_family,
            yes=yes,
            quiet=quiet,
            use_template_schema=use_template_schema,
        )
        family_name = upstream_conf_yaml["name"].data

    # TODO:_get_gf_dir_content: is implemented as github graphql query,
    # but, as an alternative, could also be answered with a local
    # clone of the git repository. then _get_gf_dir_content needs a
    # unified api.
    # This could be pereferable if there's a google/fonts clone on the
    # system and e.g. if the user has a bad/no internet access or
    # is running into github api rate limits.
    #
    # if family_name can't be found:
    #    license_dir is None, gf_dir_content is an empty dict
    license_dir, gf_dir_content = _get_gf_dir_content(family_name)

    if license_dir is None:
        # The family is not specified or not found on google/fonts.
        # Can also be an user input error, but we don't handle this yet/here.
        print(f'Font Family "{family_name}" not found on Google Fonts.')
        if require_license_dir:
            license_dir = _user_input_license(yes=yes, quiet=quiet)
        if upstream_conf_yaml is None:
            # if there was no local upstream yaml
            upstream_conf_yaml = _upstream_conf_from_scratch(
                family_name,
                yes=yes,
                quiet=quiet,
                use_template_schema=use_template_schema,
            )
    else:
        print(f'Font Family "{family_name}" is on Google Fonts under "{license_dir}".')

    if upstream_conf_yaml is not None:
        # loaded from_file or created from_scratch
        return upstream_conf_yaml, license_dir, gf_dir_content or {}

    upstream_yaml_text: typing.Union[str, None] = None
    metadata_text: typing.Union[str, None] = None

    if "upstream.yaml" in gf_dir_content:
        # normal case
        print(f"Using upstream.yaml from google/fonts for {family_name}.")
        file_sha = gf_dir_content["upstream.yaml"]["oid"]
        response = GitHubClient("google", "fonts").get_blob(file_sha)
        upstream_yaml_text = response.text

    if "METADATA.pb" in gf_dir_content:
        file_sha = gf_dir_content["METADATA.pb"]["oid"]
        response = GitHubClient("google", "fonts").get_blob(file_sha)
        metadata_text = response.text

    if upstream_yaml_text is None and metadata_text is None:
        raise Exception(
            "Unexpected: can't use google fonts family data " f"for {family_name}."
        )

    upstream_conf_yaml = _upstream_conf_from_yaml_metadata(
        upstream_yaml_text,
        metadata_text,
        yes=yes,
        quiet=quiet,
        use_template_schema=use_template_schema,
    )

    return upstream_conf_yaml, license_dir, gf_dir_content or {}


def edit_upstream_info(
    upstream_conf_yaml: YAML, file_or_family: str, is_file: bool, yes: bool, quiet: bool
) -> typing.Tuple[YAML, str, dict]:
    license_dir = None
    gf_dir_content: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

    print(f"Edit upstream conf.")
    upstream_conf_yaml = _repl_upstream_conf(
        upstream_conf_yaml.as_yaml(), yes=yes, quiet=quiet
    )
    if is_file:
        answer = user_input(
            f"Save changed file {file_or_family}?",
            OrderedDict(y="yes", n="no"),
            default="y",
            yes=yes,
            quiet=quiet,
        )
        if answer == "y":
            with open(file_or_family, "w") as upstream_yaml_file:
                upstream_yaml_file.write(upstream_conf_yaml.as_yaml())
    family_name = upstream_conf_yaml["name"].data
    # if family_name can't be found:
    #    license_dir is None, gf_dir_content is an empty dict
    license_dir, gf_dir_content = _get_gf_dir_content(family_name)
    if license_dir is None:
        # The family is not specified or not found on google/fonts.
        # Can also be an user input error, but we don't handle this yet/here.
        print(f'Font Family "{family_name}" not found on Google Fonts.')
        license_dir = _user_input_license(yes=yes, quiet=quiet)

    return upstream_conf_yaml, license_dir, gf_dir_content or {}


def output_upstream_yaml(
    file_or_family: typing.Union[str, None],
    target: str,
    yes: bool,
    quiet: bool,
    force: bool,
) -> None:
    if not file_or_family:
        # just use the template
        upstream_conf_yaml = dirty_load(
            upstream_yaml_template, upstream_yaml_template_schema, allow_flow_style=True
        )
    else:
        is_file = _file_or_family_is_file(file_or_family)
        upstream_conf_yaml, _, _ = get_upstream_info(
            file_or_family,
            is_file,
            yes,
            quiet,
            require_license_dir=False,
            use_template_schema=True,
        )
    # save!
    while True:
        try:
            with open(target, "x" if not force else "w") as f:
                f.write(upstream_conf_yaml.as_yaml())
            break
        except FileExistsError:
            if not force:
                answer = user_input(
                    f"Can't override existing target file {target}"
                    " without explicit permission.",
                    OrderedDict(f="force override", q="quit program"),
                    default="q",
                    yes=yes,
                    quiet=quiet,
                )
            if answer == "q":
                raise UserAbortError(
                    "Can't override existing target file "
                    f"{target}. "
                    "Use --force to allow explicitly."
                )
            else:  # answer == 'f'
                force = True
                continue
    print(f"DONE upstream conf saved as {target}!")


def _user_input_license(yes: bool = False, quiet: bool = False):
    answer = user_input(
        "To add a new typeface family to Google Fonts we "
        "must know the license of the family.\n"
        "It's very likely that OFL is the license that is expected here.",
        OrderedDict(
            o="OFL: SIL Open Font License",
            a="Apache License",
            u="Ubuntu Font License",
            q="quit program",
        ),
        # the default should always be an option that does
        # not require user interaction. That way we can
        # have an all -y/--no-confirm flag that always chooses the
        # default.
        default="o",
        yes=yes,
        quiet=quiet,
    )
    if answer == "q":
        raise UserAbortError()

    license_dir = {d[0]: d for d in LICENSE_DIRS}[answer]
    return license_dir


def _get_query_variables(
    repo_owner, repo_name, family_name, reference="refs/heads/main"
):
    """
    call like: get_query_variables('google', 'fonts', 'gelasio')

    reference: see $ git help rev-parse
              and git help revisions
              and https://git-scm.com/book/en/v2/Git-Internals-Git-References
    For a branch called "main", "refs/heads/main" is best
    but "main" would work as well.
    Tag names work as well, ideally "ref/tags/v0.6.8" but "v0.6.8" would
    work too. The full name is less ambiguous.
    """
    return {
        "repoOwner": repo_owner,
        "repoName": repo_name,
        "reference": reference,
        "oflDir": f"{reference}:ofl/{family_name}",
        "apacheDir": f"{reference}:apache/{family_name}",
        "uflDir": f"{reference}:ufl/{family_name}",
    }


def get_gh_gf_family_entry(family_name):
    # needs input sanitation
    family_name_normal = _family_name_normal(family_name)
    variables = _get_query_variables("google", "fonts", family_name_normal)

    result = GitHubClient("google", "fonts")._run_graphql(
        GITHUB_GRAPHQL_GET_FAMILY_ENTRY, variables
    )
    return result


def _get_gf_dir_content(
    family_name: str,
) -> typing.Tuple[
    typing.Union[str, None], typing.Dict[str, typing.Dict[str, typing.Any]]
]:
    gfentry = get_gh_gf_family_entry(family_name)
    entries = None
    for license_dir in LICENSE_DIRS:
        if gfentry["data"]["repository"][license_dir] is not None:
            entries = gfentry["data"]["repository"][license_dir]["entries"]
            break
    if entries is None:
        return None, {}
    gf_dir_content = {f["name"]: f for f in entries}
    return license_dir, gf_dir_content
