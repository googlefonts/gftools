from gftools.spec import generate_spec


if len(sys.argv) != 2:
    print("Usage: gftools gen-spec out.md")

out = sys.argv[1]

text = generate_spec()

with open(out, "w") as doc:
    doc.write(text)
