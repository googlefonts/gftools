from gftools.push import parse_server_file
from pathlib import Path
from dataclasses import dataclass


CATEGORIES = (
    "New",
    "Upgrade",
    "Other",
    "Designer profile",
    "Axis Registry",
    "Knowledge",
    "Metadata / Description / License",
    "Sample texts"
)


query = """
{
  organization(login: "google") {
    projectV2(number: 74) {
      id
      title
      items(last: 40) {
        nodes {
          id
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
          type
          content {
            ... on PullRequest {
              id
              files(first: 10) {
                nodes {
                  path
                }
              }
              url
              labels(first: 10) {
                nodes {
                  name
                }
              }
            }
          }
        }
      }
    }
  }
}
"""



@dataclass
class PushItem:
    path: Path
    type: str
    status: str
    url: str

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
    
    def __hash__(self):
        return hash((self.path, self.type, self.status, self.url))


def parse_server_file(fp, status):
    results = []
    with open(fp) as doc:
        lines = doc.read().split("\n")
        category = "Unknown"
        for line in lines:
            if not line:
                continue
            if line.startswith("#"):
                category = line[1:].strip()
            elif "#" in line:
                path, url = line.split("#")
                item = PushItem(path.strip(), category, status, url.strip())
                results.append(item)
    return results


def pr_directories(fps):
    from gftools.push import repo_path_to_google_path
    results = set()
    files = [Path(fp) for fp in fps]
    for f in files:
        path = f
        if path.suffix == ".textproto" and any(d in path.parts for d in ("lang", "axisregistry")):
            results.add(repo_path_to_google_path(path))
        else:
            path = path.parent
            # If a noto article has been updated, just return the family dir
            # ofl/notosans/article --> ofl/notosans
            if "article" in path.parts:
                path = path.parent
            results.add(str(path))
    return results



def from_graphql():
    from gftools.github import GitHubClient
    g = GitHubClient("google", "fonts")
    data = g._run_graphql(query, {})

    board_items = data["data"]["organization"]["projectV2"]["items"]["nodes"]
    results = []
    for item in board_items:
        status = item.get("status", {}).get("name", None)

        if "labels" not in item["content"]:
            print("PR missing labels. Skipping")
        labels = [i["name"] for i in item["content"]["labels"]["nodes"]]
        
        files = [i["path"] for i in item["content"]["files"]["nodes"]] 
        url = item["content"]["url"]
        directories = pr_directories(files)

        # get pr state
        if "-- blocked" in labels:
            cat = "Blocked"
        if "I Font Upgrade" in labels or "I Small Fix" in labels:
            cat = "Upgrade"
        elif "I New Font" in labels:
            cat = "New"
        elif "I Description/Metadata/OFL" in labels:
            cat = "Metadata / Description / License"
        elif "I Designer profile" in labels:
            cat = "Designer profile"
        elif "I Knowledge" in labels:
            cat = "Knowledge"
        elif "I Axis Registry" in labels:
            cat = "Axis Registry"
        elif "I Lang" in labels:
            cat = "Sample texts"
        else:
            cat = "Other"


        for directory in directories:
            results.append(
                PushItem(directory, cat, status, url)
            )
    return results


def write_server_file(items):
    from collections import defaultdict
    bins = defaultdict(set)
    for item in items:
        bins[item.type].add(item)
    
    res = []
    for tag in CATEGORIES:
        if tag not in bins:
            continue
        res.append(f"# {tag}")
        for item in bins[tag]:
            res.append(f"{item.path} # {item.url}")
        res.append("")
    return "\n".join(res)


def main():
    traffic_jam = from_graphql()
    
    # Sandbox
    traffic_sandbox = [i for i in traffic_jam if i.status == 'In Dev / PR Merged']
    sandbox_file = parse_server_file("/Users/marcfoley/Type/fonts/to_sandbox.txt", 'In Dev / PR Merged')
    sandbox = set(traffic_sandbox + sandbox_file)
    print(write_server_file(sandbox))

    import pdb
    pdb.set_trace()






if __name__ == "__main__":
    main()