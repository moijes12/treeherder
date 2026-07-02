from github import Auth, Github

from treeherder.config.settings import GITHUB_TOKEN
from treeherder.utils.http import fetch_json

if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github = Github(auth=auth)
else:
    github = Github()


def fetch_api(path, params=None):
    """
    Deprecated: use PyGithub's github instance instead.
    """
    return fetch_api_full_url(f"https://api.github.com/{path}", params)


def fetch_api_full_url(url, params=None):
    """
    Deprecated: use PyGithub's github instance instead.
    """
    if GITHUB_TOKEN:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    else:
        headers = {}
    return fetch_json(url, params, headers)


def get_releases(owner, repo, params=None):
    repository = pygithub_get_repo(owner, repo)
    releases = repository.get_releases()
    if params and "number" in params:
        return [release.raw_data for release in releases[: params["number"]]]
    return [release.raw_data for release in releases]


def get_repo(owner, repo, params=None):
    """
    Deprecated: use pygithub_get_repo instead.
    """
    return pygithub_get_repo(owner, repo).raw_data


def pygithub_get_repo(owner, repo):
    return github.get_repo(f"{owner}/{repo}")


def compare_shas(owner, repo, base, head):
    repository = pygithub_get_repo(owner, repo)
    comparison = repository.compare(base, head)
    return [commit for commit in comparison.commits]


def get_all_commits(owner, repo, params=None):
    repository = pygithub_get_repo(owner, repo)
    gh_options = {}
    if params:
        if "since" in params:
            gh_options["since"] = params["since"]
        if "sha" in params:
            gh_options["sha"] = params["sha"]

    commits = repository.get_commits(**gh_options)
    if params and "number" in params:
        return [commit.raw_data for commit in commits[: params["number"]]]
    return [commit.raw_data for commit in commits]


def get_commit(owner, repo, sha, params=None):
    repository = pygithub_get_repo(owner, repo)
    return repository.get_commit(sha).raw_data


def get_pull_request(owner, repo, pr_id):
    repository = pygithub_get_repo(owner, repo)
    return repository.get_pull(pr_id)


def get_pull_request_commits(owner, repo, pr_id):
    pr = get_pull_request(owner, repo, pr_id)
    return [commit for commit in pr.get_commits()]
