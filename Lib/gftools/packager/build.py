import contextlib
import os
import re
import selectors
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List
from venv import EnvBuilder

import git
import yaml
from rich import progress
from rich.progress import Progress

import gftools.fonts_public_pb2 as fonts_pb2

# Python <3.11
if not hasattr(contextlib, "chdir"):
    from contextlib import AbstractContextManager

    class chdir(AbstractContextManager):
        """Non thread-safe context manager to change the current working directory."""

        def __init__(self, path):
            self.path = path
            self._old_cwd = []

        def __enter__(self):
            self._old_cwd.append(os.getcwd())
            os.chdir(self.path)

        def __exit__(self, *excinfo):
            os.chdir(self._old_cwd.pop())

    contextlib.chdir = chdir


class GitRemoteProgress(git.RemoteProgress):
    OP_CODES = [
        "BEGIN",
        "CHECKING_OUT",
        "COMPRESSING",
        "COUNTING",
        "END",
        "FINDING_SOURCES",
        "RECEIVING",
        "RESOLVING",
        "WRITING",
    ]
    OP_CODE_MAP = {
        getattr(git.RemoteProgress, _op_code): _op_code for _op_code in OP_CODES
    }

    def __init__(self, progressbar, task, name) -> None:
        super().__init__()
        self.progressbar = progressbar
        self.task = task
        self.name = name
        self.curr_op = None

    @classmethod
    def get_curr_op(cls, op_code: int) -> str:
        """Get OP name from OP code."""
        # Remove BEGIN- and END-flag and get op name
        op_code_masked = op_code & cls.OP_MASK
        return cls.OP_CODE_MAP.get(op_code_masked, "?").title()

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str | None = "",
    ) -> None:
        if not self.progressbar:
            return
        # Start new bar on each BEGIN-flag
        if op_code & self.BEGIN:
            self.curr_op = self.get_curr_op(op_code)
            # logger.info("Next: %s", self.curr_op)
            self.progressbar.update(
                self.task,
                description="[yellow] " + self.curr_op + " " + self.name,
                total=max_count,
            )

        self.progressbar.update(
            task_id=self.task,
            completed=cur_count,
            message=message,
        )


def find_config_yaml(source_dir: Path):
    configs = []
    for path in source_dir.glob("sources/*.y*l"):
        if not (str(path).endswith(".yaml") or str(path).endswith(".yml")):
            continue
        content = yaml.load(path.read_text(), Loader=yaml.Loader)
        if "sources" not in content:
            continue
        configs.append(path)
    if configs:
        return configs[0]


def find_sources(source_dir: Path) -> List[Path]:
    # Extensions in order of preference
    for extension in [".glyphs", ".glyphspackage", ".designspace", ".ufo"]:
        sources = list(source_dir.glob("sources/*" + extension))
        if sources:
            return sources
    return []


class SourceBuilder:
    def __init__(
        self,
        destination: Path,
        family_path: Path,
        metadata: fonts_pb2.FamilyProto,
        their_venv: bool = False,
    ):
        self.destination = destination
        self.family_path = family_path
        self.metadata = metadata
        self.name = metadata.name
        self.their_venv = their_venv
        self.progressbar = None
        self.source_dir = tempfile.TemporaryDirectory()

    def setup_venv(self, source_dir: Path):
        venv_task = self.progressbar.add_task(
            "[yellow]Setup venv", total=500, visible=False
        )
        self.progressbar.update(
            venv_task,
            description="[yellow] Setting up venv for " + self.name + "...",
            completed=0,
            visible=True,
        )
        if (source_dir / "Makefile").exists():
            with contextlib.chdir(source_dir):
                # self.progressbar.console.print(
                #     "[yellow]Running make venv in " + str(source_dir)
                # )
                rc = self.run_command_with_callback(
                    ["make", "venv"],
                    lambda line: self.progressbar.update(venv_task, advance=1),
                )
        elif (source_dir / "requirements.txt").exists():
            builder = EnvBuilder(system_site_packages=False, with_pip=True)
            builder.create(str(source_dir / "venv"))
            self.progressbar.update(venv_task, completed=10)
            # self.progressbar.console.print(
            #     "[yellow]Running pip install in " + str(source_dir)
            # )
            with contextlib.chdir(source_dir):
                rc = self.run_command_with_callback(
                    ["venv/bin/pip", "install", "-r", "requirements.txt"],
                    lambda line: self.progressbar.update(venv_task, advance=1),
                )
        else:
            raise ValueError(
                "--their-venv was provided but no Makefile or requirements.txt upstream"
            )
        if rc != 0:
            self.progressbar.console.print(
                "[red]Error setting up venv for " + self.name
            )
            raise ValueError("Venv setup failed")
        self.progressbar.remove_task(venv_task)

    def local_overrides(
        self, upstream: Path, downstream: Path, overrides: Dict[str, str]
    ):
        for source, dest in overrides.items():
            if (downstream / source).exists():
                dest_path = upstream / dest
                os.makedirs(dest_path.parent, exist_ok=True)
                self.progressbar.console.print("[grey]Using our " + source)
                shutil.copy(downstream / source, dest_path)

    def build(self):
        with Progress(
            progress.TimeElapsedColumn(),
            progress.TextColumn("[progress.description]{task.description}"),
            progress.BarColumn(),
            progress.TextColumn("{task.completed}/{task.total}"),
            progress.TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            progress.TimeRemainingColumn(),
        ) as self.progressbar:
            with tempfile.TemporaryDirectory() as source_dir:
                source_dir = Path(source_dir)
                self.clone_source(source_dir)
                self.local_overrides(
                    source_dir,
                    self.family_path,
                    {
                        "config.yaml": "sources/config.yaml",
                        "requirements.txt": "requirements.txt",
                    },
                )

                if not (source_dir / "sources").exists():
                    raise ValueError(f"Could not find sources directory in {self.name}")
                if self.their_venv:
                    self.setup_venv(source_dir)

                # Locate the config.yaml file or first source
                arg = find_config_yaml(source_dir)
                if not arg:
                    sources = find_sources(source_dir)
                    if not sources:
                        raise ValueError(
                            f"Could not find any sources in {self.metadata.source}"
                        )
                    arg = sources[0]

                with contextlib.chdir(source_dir):
                    if self.their_venv:
                        buildcmd = ["venv/bin/gftools-builder", str(arg)]
                    else:
                        buildcmd = ["gftools-builder", str(arg)]
                    self.run_build_command(buildcmd)
                    self.copy_files()

    def run_command_with_callback(self, cmd, callback):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        sel = selectors.DefaultSelector()
        sel.register(process.stdout, selectors.EVENT_READ)
        sel.register(process.stderr, selectors.EVENT_READ)
        ok = True
        stdoutlines = []
        stderrlines = []
        while ok:
            for key, _val1 in sel.select():
                line = key.fileobj.readline()
                if not line:
                    ok = False
                    break
                if key.fileobj is process.stdout:
                    callback(line)
                elif key.fileobj is process.stderr:
                    stderrlines.append(line)
                else:
                    stdoutlines.append(line)
        rc = process.wait()
        if rc != 0:
            for line in stdoutlines:
                self.progressbar.console.print(line.decode("utf-8"), end="")
            for line in stderrlines:
                self.progressbar.console.print("[red]" + line.decode("utf8"), end="")
        return rc

    def run_build_command(self, buildcmd):
        build_task = self.progressbar.add_task("[green]Build " + self.name, total=1)

        def progress_callback(line):
            if m := re.match(r"^\[(\d+)/(\d+)\]", line.decode("utf8")):
                self.progressbar.update(
                    build_task, completed=int(m.group(1)), total=int(m.group(2))
                )

        if self.run_command_with_callback(buildcmd, progress_callback) != 0:
            self.progressbar.console.print("[red]Error building " + self.name)
            raise ValueError("Build failed")
        else:
            self.progressbar.console.print("[green]Built " + self.name)

    def clone_source(
        self,
        builddir: Path,
    ):
        clone_task = self.progressbar.add_task(
            "[yellow]Clone", total=100, visible=False
        )
        self.progressbar.update(
            clone_task,
            description="[yellow] Cloning " + self.name + "...",
            completed=0,
            visible=True,
        )
        git.Repo.clone_from(
            url=self.metadata.source.repository_url,
            to_path=builddir,
            depth=1,
            progress=GitRemoteProgress(self.progressbar, clone_task, self.name),
        )
        self.progressbar.remove_task(clone_task)

    def copy_files(self):
        # We are sat in the build directory
        for item in self.metadata.source.files:
            in_fp = Path(item.source_file)
            if not in_fp.exists():
                raise ValueError(
                    f"Expected to copy {item.source_file} but it was not found after build"
                )
            out_fp = Path(self.destination / item.dest_file)
            if not out_fp.parent.exists():
                os.makedirs(out_fp.parent, exist_ok=True)
            shutil.copy(in_fp, out_fp)


def build_to_directory(
    destination: Path,
    family_path: Path,
    metadata: fonts_pb2.FamilyProto,
    their_venv: bool = False,
):
    SourceBuilder(destination, family_path, metadata, their_venv).build()
