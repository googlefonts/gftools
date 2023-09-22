from collections import defaultdict
import importlib
from os import chdir
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile, gettempdir
from typing import Tuple
import yaml
from dataclasses import dataclass
import os.path
import networkx as nx
from ninja.ninja_syntax import Writer, escape_path
from fontmake.font_project import FontProject

from gftools.builder.file import File
from gftools.builder.operations import OperationBase, known_operations
from gftools.builder.operations.copy import Copy
from gftools.builder.recipeproviders import get_provider

def edge_with_operation(node, operation):
    for newnode, attributes in node.items():
        if operation == attributes.get("operation"):
            return newnode
    return None


class GFBuilder:
    def __init__(self, config):
        with open(config, "r") as file:
            self.config = yaml.safe_load(file)
        chdir(Path(config).resolve().parent)
        self.writer = Writer(open("build.ninja", "w"))
        self.named_files = {}
        self.used_operations = set([])
        self.graph = nx.DiGraph()

        if "recipeProvider" not in self.config and "recipe" not in self.config:
            self.config["recipeProvider"] = "googlefonts"

        if "recipeProvider" in self.config:
            # Store the automatic recipe but allow user-defined steps to override
            automatic_recipe = self.call_recipe_provider()
            self.config["recipe"] = { **automatic_recipe, **self.config.get("recipe",{}) }
        self.validate_recipe(self.config)

    # The builder proceeds in four steps. The first step is to prepare
    # the recipe, in YAML-like objects. If there isn't a recipe, we use
    # a recipe provider to create one. Once we have one, we do some basic
    # validation checks on the recipe.

    def call_recipe_provider(self):
        provider = get_provider(self.config["recipeProvider"])
        return provider(self.config, self).write_recipe()

    def validate_recipe(self, config):
        recipe = self.config["recipe"]
        for target, steps in recipe.items():
            if steps[0].get("source") is None:
                raise ValueError("First step must have a 'source' key")
            seen_postprocess = False
            for step in steps:
                if "operation" in step:
                    if seen_postprocess:
                        raise ValueError(
                            f"Seen operation step '{step['operation']}' after postprocessing step in {target}"
                        )
                elif "postprocess" in step:
                    seen_postprocess = True

    # The next step is to turn the recipe into a set of Python objects;
    # these can store a bit more information than our simple YAML-like
    # data.
    def config_to_objects(self):
        recipe = self.config["recipe"]
        for target, steps in recipe.items():
            newsteps = []
            for step in steps:
                if "source" in step:
                    newsteps.append(self.source_step_to_object(step))
                elif "operation" in step:
                    newsteps.append(self.operation_step_to_object(step))
                elif "postprocess" in step:
                    newsteps.append(self.postprocess_step_to_object(step))
                else:
                    raise ValueError(f"Unknown step type: {step}")
            steps[:] = newsteps

    def source_step_to_object(self, step):
        source: str = step["source"]
        return self._ensure_named_file(source, type="source")

    def glyphs_to_ufo(self, source):
        source = Path(source)
        directory = source.resolve().parent
        output = str(Path(directory) / source.with_suffix(".designspace").name)
        FontProject().run_from_glyphs(
            str(source.resolve()),
            **{
                "format": ["ufo"],
                "output": ["ufo"],
                "output_dir": directory,
                "master_dir": directory,
                "designspace_path": output,
            },
        )
        return source.with_suffix(".designspace").name
    
    def operation_step_to_object(self, step):
        operation = step.get("operation") or step.get("postprocess")
        if operation not in known_operations:
            raise ValueError(f"Unknown operation {operation}")
        cls = known_operations[operation]
        if operation not in self.used_operations:
            self.used_operations.add(operation)
            cls.write_rules(self.writer)
        step = cls(original=step)
        step.convert_dependencies(self)
        return step

    def postprocess_step_to_object(self, step):
        obj = self.operation_step_to_object(step)
        obj.postprocess = True
        return obj

    # The third step is to build a graph and sew together the objects
    # such that the output step of one is fed is the input to the next,
    # and vice versa.
    def build_graph(self):
        Copy().write_rules(self.writer)
        for target, steps in self.config["recipe"].items():
            if target not in self.named_files:
                self._ensure_named_file(target, type="binary")
            for step in steps:
                if isinstance(step, File):
                    self.graph.add_node(step)

        for target, steps in self.config["recipe"].items():
            self._build_graph(target, steps)

    def _ensure_named_file(self, file, type="binary"):
        if file not in self.named_files:
            self.named_files[file] = File(file, type)
            self.graph.add_node(self.named_files[file])
        return self.named_files[file]

    def _build_graph(self, target, steps):
        current = None
        if not isinstance(target, File):
            target = self.named_files[target]
        if target not in self.graph:
            self.graph.add_node(target)
        all_operations = [
            s for s in steps if isinstance(s, OperationBase) and not s.postprocess
        ]
        if not all_operations:
            raise ValueError(f"No operations in {target}")
        last_operation = all_operations[-1]
        binary = None
        for ix, step in enumerate(steps):
            if isinstance(step, File):
                # This is a source: entry, saying that we should either
                # start the build process with a particular source, or
                # switch to a new source midway through.
                if current:
                    if current.path is None:
                        current.path = step.path
                        current = step
                    elif current.path != step.path:
                        # We did something, and now we are switching source.
                        # We assume that this new source has been produced
                        # by the previous operation. So walk backwards,
                        # find that operation, and add this as an out-node.
                        parents = list(self.graph.predecessors(current))
                        if len(parents) != 1:
                            raise ValueError(
                                f"Multiple rules apparently produced {current.path}"
                            )
                        edge = self.graph[parents[0]][current]
                        # print("Adding edge, ", parents[0], step, edge)
                        self.graph.add_edge(parents[0], step, **edge)
                current = step
            else:
                # This is an ordinary operation.
                if current is None:
                    # We need to start somewhere!
                    raise ValueError(f"Operation without source in target {target}")

                # If there is an edge from the source to the operation, then follow it
                # This means that another target has also depended on this operation.
                existing_edge = edge_with_operation(self.graph[current], step)
                # XXX handle postprocessing operations here
                previous = current
                if existing_edge:
                    # print(f"Found an edge from {current.path} via {step.opname}")
                    current = existing_edge
                    # If we are expecting a different target name, copy the
                    # file to rename it.
                    if current.path != target.path and step == last_operation:
                        # print(f"Expected it to be {target.path}, copying")
                        copy_operation = Copy()
                        copy_operation.set_source(current)
                        copy_operation.set_target(target)
                        self.graph.add_edge(current, target, operation=copy_operation)
                        current = target
                else:
                    # We are the first to run this operation, so we need to
                    # create a new edge in the graph.
                    if step.postprocess:
                        # In a post-processing step, we expect:
                        # The target is the stamp file
                        # The source is the terminal binary
                        # The implicit files are any previous stamp files
                        binary = File(step.stamppath)
                        self.graph.add_node(binary)
                        step._sources = last_operation.targets
                        parents = list(self.graph.predecessors(current))
                        previous_edge = self.graph[parents[0]][current]
                        step.implicit = [current]
                        self.graph.add_edge(current, binary, operation=step)
                    else:
                        step.set_source(previous)
                        if step == last_operation:
                            binary = target
                            binary.terminal = True
                            step.set_target(binary)
                        elif step.targets: #  Step already knows its own target
                            binary = step.targets[0]
                        else:
                            binary = File(NamedTemporaryFile().name)
                            self.graph.add_node(binary)
                            step.set_target(binary)
                        self.graph.add_edge(current, binary, operation=step)
                    # print(
                    #     f"Creating an edge from {current.path} to {binary} via {step.opname}"
                    # )
                    current = binary

    # Finally we walk the graph. We do another validation pass to make
    # sure that the operations make sense, and then we emit the ninja rules.
    def walk_graph(self):
        actions = defaultdict(list)
        final_targets = []
        for source, target in nx.algorithms.traversal.edge_bfs(self.graph):
            edge = self.graph[source][target]
            if "operation" not in edge:
                continue  # ???
            edge["operation"].validate()
            actions[(source, edge["operation"])].append(target)
            if not list(self.graph.successors(target)):
                final_targets.append(escape_path(target.path))

        for (source, operation), targets in actions.items():
            operation.build(self.writer)

        assert len(final_targets), "No final targets"
        self.writer.default(final_targets)
        self.writer.close()

    def draw_graph(self):
        import pydot

        dot = subprocess.run(["ninja", "-t", "graph"], capture_output=True)
        graphs = pydot.graph_from_dot_data(dot.stdout.decode("utf-8"))
        targets = self.config["recipe"].keys()
        if graphs and graphs[0]:
            for g in graphs[0].get_nodes():
                if g.get_label() and g.get_label().endswith('stamp"'):
                    g.set_style("filled")
                    g.set_fillcolor("#ffcccc")
                    g.set_label("Stamp")
                elif g.get_label() and g.get_label().startswith('"'+gettempdir()):
                    g.set_style("filled")
                    g.set_fillcolor("#ffcccc")
                    g.set_label("Tempfile")
                elif g.get_label() and g.get_label()[1:-1] in targets:
                    g.set_style("filled")
                    g.set_fillcolor("#ccccff")
            graphs[0].write_png("graph.png")
        else:
            print("Could not parse ninja build file")

def main(args=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", help="Draw a graph of the build process", action="store_true")
    parser.add_argument("--no-ninja", help="Do not run ninja", action="store_true")
    parser.add_argument("--generate", help="Just generate and output recipe from recipe builder", action="store_true")
    parser.add_argument("config", help="Path to config file")
    args = parser.parse_args(args)
    pd = GFBuilder(args.config)
    if args.generate:
        print(yaml.dump(pd.config))
        return
    pd.config_to_objects()
    pd.build_graph()
    pd.walk_graph()
    if args.graph:
        pd.draw_graph()
    if not args.no_ninja:
        subprocess.run(["ninja"])
