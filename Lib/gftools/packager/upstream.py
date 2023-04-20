# Things dealing with upstream.yaml files

import typing
from typing import TYPE_CHECKING
from collections import OrderedDict

from pkg_resources import resource_filename
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
    GITHUB_GRAPHQL_GET_FAMILY_ENTRY,
    LICENSE_DIRS,
    NOTO_GITHUB_URL,
)

from gftools.packager.exceptions import UserAbortError, ProgramAbortError

# Copied from packager, needs moving later


def _file_or_family_is_file(file_or_family: str) -> bool:
    return file_or_family.endswith(".yaml") or file_or_family.endswith(
        ".yml"
    )  # .yml is common, too


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


def normalize_family_name(name):
    return name.lower().replace(" ", "").replace(".", "").replace("/", "")


class UpstreamConfig:
    upstream_yaml: YAML

    def __init__(self, upstream_yaml: YAML):
        self.upstream_yaml = upstream_yaml

    @classmethod
    def template(cls):
        return cls.load(upstream_yaml_template, use_template_schema=True)

    @classmethod
    def load(
        cls,
        upstream_yaml_text: str,
        use_template_schema: bool = False,
    ):
        try:
            yaml_schema = (
                upstream_yaml_schema
                if not use_template_schema
                else upstream_yaml_template_schema
            )
            yaml = dirty_load(upstream_yaml_text, yaml_schema, allow_flow_style=True)
        except YAMLValidationError as err:
            print("The configuration has schema errors:\n\n" f"{err}")
            raise ProgramAbortError()
        return UpstreamConfig(yaml)

    @classmethod
    def from_file(cls, filename, use_template_schema: bool = False):
        with open(filename, "r+") as upstream_yaml_file:
            upstream_yaml_text = upstream_yaml_file.read()
            return cls.load(
                upstream_yaml_text,
                use_template_schema=use_template_schema,
            )

    @classmethod
    def from_scratch(
        cls,
        family_name: typing.Union[str, None] = None,
        use_template_schema: bool = False,
    ) -> YAML:

        upstream_conf_yaml = dirty_load(
            upstream_yaml_template, upstream_yaml_template_schema, allow_flow_style=True
        )
        if family_name is not None:
            upstream_conf_yaml["name"] = family_name

        assert use_template_schema, "from_scratch called in non-interactive mode"

        return UpstreamConfig(upstream_conf_yaml)

    def format(self, compact: bool = True):
        # removes comments to make it more compact to read
        if compact:
            description = "upstream configuration (no comments, normalized)"
            content = as_document(
                self.upstream_yaml.data, upstream_yaml_schema
            ).as_yaml()
        else:
            description = "upstream configuration"
            content = self.as_text()
        len_top_bars = (58 - len(description)) // 2
        top = f'{"-"*len_top_bars} {description} {"-"*len_top_bars}'
        return f"{top}\n" f"{content}" f'{"-"*len(top)}'

    @property
    def present_data(self):
        """Returns a dictionary of values which are not None"""
        return {k: v for k, v in self.upstream_yaml.data.items() if v is not None}

    def all_data(self):
        return self.upstream_yaml.data

    @property
    def family_name(self):
        return self.upstream_yaml["name"].data

    @property
    def normalized_family_name(self):
        return normalize_family_name(self.family_name)

    def as_text(self):
        return self.upstream_yaml.as_yaml()

    def save(self, target, force=False):
        try:
            with open(target, "x" if not force else "w") as f:
                f.write(self.as_text())
        except FileExistsError:
            if not force:
                raise UserAbortError(
                    "Can't override existing target file "
                    f"{target}. "
                    "Use --force to allow explicitly."
                )
        print(f"DONE upstream conf saved as {target}!")

    def get(self, key):
        return self.upstream_yaml[key].data

    def set(self, key, value):
        self.upstream_yaml[key] = value

    def save_backup(self):
        family_name_normal = self.normalized_family_name
        count = 0
        while True:
            counter = "" if count == 0 else f"_{count}"
            filename = f"./{family_name_normal}.upstream{counter}.yaml"
            try:
                # 'x': don't override existing files
                with open(filename, "x") as f:
                    f.write(self.as_text())
            except FileExistsError:
                # retry until the file could be created, file name changes
                count += 1
                continue
            break
        return filename

    def stripped(self):
        redundant_keys = {"name", "category", "designer", "repository_url"}
        upstream_conf_stripped = OrderedDict(
            (k, v)
            for k, v in self.upstream_yaml.data.items()
            if k not in redundant_keys
        )
        # Don't keep an empty build key.
        if "build" in upstream_conf_stripped and (
            upstream_conf_stripped["build"] == ""
            or upstream_conf_stripped["build"] is None
        ):
            del upstream_conf_stripped["build"]
        return UpstreamConfig(
            as_document(upstream_conf_stripped, upstream_yaml_stripped_schema)
        )

    def fill_metadata(self, metadata):
        """Copy information from upstream.yml into the metadata.pb"""
        metadata.name = self.get("name")
        for font in metadata.fonts:
            font.name = self.get("name")
        metadata.designer = self.get("designer")

        metadata.category[:] = self.get("category")

        # metadata.date_added # is handled well

        metadata.source.repository_url = self.get("repository_url")

        if self.get("repository_url").startswith(NOTO_GITHUB_URL):
            metadata.is_noto = True


def _upstream_conf_from_yaml_metadata(
    upstream_yaml_text: typing.Union[str, None],
    metadata_text: typing.Union[str, None],
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
        upstream_conf_yaml = UpstreamConfig.load(
            upstream_yaml_text, use_template_schema=True
        )
        # Override keys set by METADATA.pb before, if there's overlap.
        upstream_conf.update(upstream_conf_yaml.present_data)

    upstream_conf_yaml = UpstreamConfig.template()
    for k, v in upstream_conf.items():
        if v is None:
            continue
        upstream_conf_yaml.set(k, v)

    upstream_yaml_text = upstream_conf_yaml.as_text()
    assert upstream_yaml_text is not None

    return UpstreamConfig.load(
        upstream_yaml_text,
        use_template_schema=use_template_schema,
    )


def get_upstream_info(
    file: str,
    family_name: str,
    require_license_dir: bool = True,
    use_template_schema: bool = False,
) -> typing.Tuple[YAML, typing.Union[str, None], dict]:
    # the first task is to acquire an upstream_conf, the license dir and
    # if present the available files for the family in the google/fonts repo.
    license_dir: typing.Union[str, None] = None
    upstream_conf = None
    gf_dir_content: typing.Dict[str, typing.Dict[str, typing.Any]] = {}

    if file:
        upstream_conf = UpstreamConfig.from_file(
            file,
            use_template_schema=use_template_schema,
        )
        family_name = upstream_conf.family_name

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
            print("Assuming OFL")
            license_dir = "ofl"
        if upstream_conf is None:
            # if there was no local upstream yaml
            upstream_conf = UpstreamConfig.from_scratch(
                family_name,
                use_template_schema=use_template_schema,
            )
    else:
        print(f'Font Family "{family_name}" is on Google Fonts under "{license_dir}".')

    if upstream_conf is not None:
        # loaded from_file or created from_scratch
        return upstream_conf, license_dir, gf_dir_content or {}

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

    upstream_conf = _upstream_conf_from_yaml_metadata(
        upstream_yaml_text,
        metadata_text,
        use_template_schema=use_template_schema,
    )

    return upstream_conf, license_dir, gf_dir_content or {}


def output_upstream_yaml(args) -> None:
    if not args.family:
        # use the template
        upstream_conf = UpstreamConfig.template()
    else:
        upstream_conf, _, _ = get_upstream_info(
            None,
            args.family,
            require_license_dir=False,
            use_template_schema=True,
        )
    upstream_conf.save(args.target, force=args.force)


def get_gh_gf_family_entry(family_name):
    # needs input sanitation
    family_name_normal = normalize_family_name(family_name)
    result = GitHubClient("google", "fonts")._run_graphql(
        GITHUB_GRAPHQL_GET_FAMILY_ENTRY,
        {
            "repoOwner": "google",
            "repoName": "fonts",
            "reference": "refs/heads/main",
            "oflDir": f"refs/heads/main:ofl/{family_name_normal}",
            "apacheDir": f"refs/heads/main:apache/{family_name_normal}",
            "uflDir": f"refs/heads/main:ufl/{family_name_normal}",
        },
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
