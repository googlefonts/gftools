import os
import pprint
import requests
import typing
import urllib


GITHUB_GRAPHQL_API = 'https://api.github.com/graphql'
GITHUB_V3_REST_API = 'https://api.github.com'


class GitHubClient:
    def __init__(self, repo_owner, repo_name):
        if not 'GH_TOKEN' in os.environ:
            raise Exception("GH_TOKEN environment variable not set")
        self.gh_token = os.environ['GH_TOKEN']
        self.repo_owner = repo_owner
        self.repo_name = repo_name
    
    def _post(self, url, payload: typing.Dict):
        headers = {'Authorization': f'bearer {self.gh_token}'}
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == requests.codes.unprocessable:
            # has a helpful response.json with an 'errors' key.
            pass
        else:
            response.raise_for_status()
        json = response.json()
        if 'errors' in json:
            errors = pprint.pformat(json['errors'], indent=2)
            raise Exception(f'GitHub POST query failed to url {url}:\n {errors}')
        return json
    
    def _get(self, url):
        headers = {'Authorization': f'bearer {self.gh_token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json = response.json()
        if 'errors' in json:
            errors = pprint.pformat(json['errors'], indent=2)
            raise Exception(f'GitHub REST query failed:\n {errors}')
        return json
        
    def _run_graphql(self, query, variables):
        payload = {'query': query, 'variables': variables}
        return self._post(GITHUB_GRAPHQL_API, payload)
    
    def rest_url(self, path, **kwargs):
        base_url = f'{GITHUB_V3_REST_API}/repos/{self.repo_owner}/{self.repo_name}/{path}'
        if kwargs:
            base_url += '?' + '&'.join(f'{k}={urllib.parse.quote(v)}' for k, v in kwargs.items())
        return base_url

    def get_blob(self, file_sha):
        url = self.rest_url(f'git/blobs/{file_sha}')
        headers = {
            'Accept': 'application/vnd.github.v3.raw',
            'Authorization': f'bearer {self.gh_token}'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    
    def open_prs(self, pr_head: str, pr_base_branch: str) -> typing.List:
        return self._get(self.rest_url("pulls", state="open", head=pr_head, base=pr_base_branch))
    
    def create_pr(self, title: str, body: str, head: str, base: str):
        return self._post(
            self.rest_url("pulls"),
            {
                'title': title,
                'body': body,
                'head': head,
                'base': base,
                'maintainer_can_modify': True
            }
        )
    
    def create_issue_comment(self, issue_number: int, body: str):
        return self._post(
            self.rest_url(f'issues/{issue_number}/comments'),
            {
                'body': body
            }
        )
    
    def create_issue(self, title: str, body: str):
        return self._post(
            self.rest_url("issues"),
            {
                'title': title,
                'body': body
            }
        )






