CATEGORIES = ["DISPLAY", "SERIF", "SANS_SERIF", "HANDWRITING", "MONOSPACE"]

NOTO_GITHUB_URL = "https://github.com/notofonts/"

GIT_NEW_BRANCH_PREFIX = "gftools_packager_"

GITHUB_REPO_SSH_URL = "git@github.com:{repo_name_with_owner}.git".format

# Using object(expression:$rev), we query all three license folders
# for family_name, but only the entry that exists will return a tree (directory).
# Non existing directories will be null (i.e. None).
# Hence, we can send one query to know the family exists or not, in which
# directory (license) and have a (flat) directory listing.
# I queried "rateLimit{cost}" and this had a cost of 1!
GITHUB_GRAPHQL_GET_FAMILY_ENTRY = """
fragment FamilyFiles on Tree {
  entries{
    name
    type
    oid
  }
}

query ListFiles($repoName: String!,
                $repoOwner: String!,
                $reference: String!,
                $oflDir: String!,
                $uflDir: String!,
                $apacheDir: String!
) {
  repository(name: $repoName, owner: $repoOwner) {
    ref(qualifiedName: $reference) {
      prefix
      name
      target {
        ... on Commit {
          __typename
          oid
          messageHeadline
          pushedDate
        }
      }
    }
    ofl: object(expression: $oflDir) {
      ...FamilyFiles
    }
    apache: object(expression:$apacheDir) {
      __typename
      ...FamilyFiles
    }
    ufl: object(expression:$uflDir) {
      __typename
      ...FamilyFiles
    }
  }
}
"""

# ALLOWED FILES
LICENSE_FILES_2_DIRS = (
    ("LICENSE.txt", "apache"),
    ("UFL.txt", "ufl"),
    ("OFL.txt", "ofl"),
)

# ('apache', 'ufl', 'ofl')
LICENSE_DIRS = tuple(zip(*LICENSE_FILES_2_DIRS))[1]

ALLOWED_FILES = {
    "DESCRIPTION.en_us.html",
    "FONTLOG.txt",
    "article/ARTICLE.en_us.html",
    *dict(LICENSE_FILES_2_DIRS).keys()  # just the file names/keys
    # METADATA.pb is not taken from upstream, technically we update the
    # version in google fonts or create it newly
}

