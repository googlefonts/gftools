import os
import pprint
import requests
import typing
import urllib
import time
from gftools.utils import github_user_repo

GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
GITHUB_V3_REST_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, repo_owner, repo_name):
        if not "GH_TOKEN" in os.environ:
            raise Exception("GH_TOKEN environment variable not set")
        self.gh_token = os.environ["GH_TOKEN"]
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    @classmethod
    def from_url(cls, url):
        user, repo = github_user_repo(url)
        return cls(user, repo)

    def _post(self, url, payload: typing.Dict):
        headers = {"Authorization": f"bearer {self.gh_token}"}
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == requests.codes.unprocessable:
            # has a helpful response.json with an 'errors' key.
            pass
        else:
            response.raise_for_status()
        json = response.json()
        if "errors" in json:
            errors = pprint.pformat(json["errors"], indent=2)
            raise Exception(f"GitHub POST query failed to url {url}:\n {errors}")
        return json

    def _get(self, url):
        headers = {"Authorization": f"bearer {self.gh_token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json = response.json()
        if "errors" in json:
            errors = pprint.pformat(json["errors"], indent=2)
            raise Exception(f"GitHub REST query failed:\n {errors}")
        return json

    def _run_graphql(self, query, variables):
        payload = {"query": query, "variables": variables}
        return self._post(GITHUB_GRAPHQL_API, payload)

    def rest_url(self, path, **kwargs):
        base_url = (
            f"{GITHUB_V3_REST_API}/repos/{self.repo_owner}/{self.repo_name}/{path}"
        )
        if kwargs:
            base_url += "?" + "&".join(
                f"{k}={urllib.parse.quote(v)}" for k, v in kwargs.items()
            )
        return base_url

    def get_content(self, path, branch=None):
        if branch:
            url = self.rest_url(f"contents/{path}", ref=branch)
        else:
            url = self.rest_url(f"contents/{path}")
        headers = {
            "Accept": "application/vnd.github.v3.raw",
            "Authorization": f"bearer {self.gh_token}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response

    def get_blob(self, file_sha):
        url = self.rest_url(f"git/blobs/{file_sha}")
        headers = {
            "Accept": "application/vnd.github.v3.raw",
            "Authorization": f"bearer {self.gh_token}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response

    def get_latest_release(self):
        """https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#get-the-latest-release"""
        return self._get(self.rest_url("releases/latest"))

    def get_latest_release_tag(self) -> str:
        return self.get_latest_release()["tag_name"]

    def open_prs(self, pr_head: str, pr_base_branch: str) -> typing.List:
        return self._get(
            self.rest_url("pulls", state="open", head=pr_head, base=pr_base_branch)
        )

    def get_commit(self, ref: str):
        return self._get(self.rest_url(f"commits/{ref}"))

    def create_pr(
        self, title: str, body: str, head: str, base: str, draft: bool = False
    ):
        return self._post(
            self.rest_url("pulls"),
            {
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "maintainer_can_modify": True,
                "draft": draft,
            },
        )

    def update_pr(
        self, pull_number: int, title: str = None, body: str = None, state: str = None
    ):
        return self._post(
            self.rest_url(f"pulls/{pull_number}"),
            {"title": title, "body": body, "state": state},
        )

    def create_issue_comment(self, issue_number: int, body: str):
        return self._post(
            self.rest_url(f"issues/{issue_number}/comments"), {"body": body}
        )

    def create_issue(self, title: str, body: str):
        return self._post(self.rest_url("issues"), {"title": title, "body": body})

    def pr_files(self, pr_number: int, sleep=4):
        res = []
        cur_page = 1
        url = self.rest_url(
            f"pulls/{pr_number}/files", per_page="100", page=str(cur_page)
        )
        request = self._get(url)
        while request:
            res += request
            cur_page += 1
            url = self.rest_url(
                f"pulls/{pr_number}/files", per_page="100", page=str(cur_page)
            )
            request = self._get(url)
            # sleep so we don't hit api rate limits. We should get at least 1k
            # requests per hour so sleeping for 4 secs by default means we
            # shouldn't hit any issues.
            time.sleep(sleep)
        return res

    def add_labels(self, issue_number: int, labels: typing.List[str]):
        return self._post(
            self.rest_url(f"issues/{issue_number}/labels"),
            {"labels": labels},
        )

    def get_labels(self, issue_number):
        return self._get(self.rest_url(f"issues/{issue_number}/labels"))
