from gftools.builder import GFBuilder
import yaml
import subprocess

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", help="Draw a graph of the build process", action="store_true")
    parser.add_argument("--no-ninja", help="Do not run ninja", action="store_true")
    parser.add_argument("--generate", help="Just generate and output recipe from recipe builder", action="store_true")
    parser.add_argument("config", help="Path to config file")
    args = parser.parse_args()
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
    

if __name__ == "__main__":
    main()
