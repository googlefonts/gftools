from gftools.gfgithub import GitHubClient
import pytest


@pytest.mark.parametrize(
    "pr_number,file_count",
    [
        (6874, 1),
        (6779, 3),
        (2987, 178),
        (6787, 568),
    ],
)
def test_pr_files(pr_number, file_count):
    client = GitHubClient("google", "fonts")
    assert len(client.pr_files(pr_number)) == file_count
