import subprocess
import tempfile
import os
import sys


if len(sys.argv) != 2:
    print("Usage: python builder_dependent_test.py report.txt")
    sys.exit()


repos = [
    # "https://github.com/googlefonts/Gulzar", not gftools builder!
    ("https://github.com/namelatype/Marhey", os.path.join("sources", "config.yaml")),
    ("https://github.com/erikdkennedy/figtree", os.path.join("sources", "config.yaml")),
]

report_path = sys.argv[1]
with open(report_path, "w") as doc:
    for repo, config_path in repos:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.call(["git", "clone", repo, tmpdir])
            builder_path = os.path.join(tmpdir, config_path)
            build_msg = subprocess.run(
                ["gftools", "builder", builder_path],
                capture_output=True,
                )
            doc.write(repo+"\n")
            doc.write(build_msg.stderr.decode("utf-8"))
            doc.write("\n")