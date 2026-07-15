from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from functools import lru_cache
from github import Auth, Github
from github.Repository import Repository
from github.Commit import Commit
from github.PullRequest import PullRequest
from github.GitRelease import GitRelease
from github.PaginatedList import PaginatedList

from treeherder.config.settings import GITHUB_TOKEN

if GITHUB_TOKEN:
    auth: Auth.Token = Auth.Token(GITHUB_TOKEN)
    github: Github = Github(auth=auth)
else:
    github: Github = Github()


def get_releases(owner: str, repo: str, params: Optional[Dict[str, Any]] = None) -> List[GitRelease]:
    """
    Fetch releases for a given repository.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param params: Optional parameters for filtering (e.g., 'since', 'number').
    :return: A list of PyGithub GitRelease objects.
    """
    repository: Repository = get_repo(owner, repo)
    releases: PaginatedList[GitRelease] = repository.get_releases()

    # Apply filtering by date if 'since' is provided in params
    if params and "since" in params:
        since: Union[str, datetime] = params["since"]
        if isinstance(since, str):
            from dateutil.parser import parse

            since_dt: datetime = parse(since)
        else:
            since_dt = since

        # Filtering releases where published_at > since
        releases = [r for r in releases if r.published_at and r.published_at > since_dt]

    if params and "number" in params:
        # Replicating the old behavior where params['number'] limited the results
        return [release for release in releases[: params["number"]]]
    return [release for release in releases]


@lru_cache(maxsize=10)
def get_repo(owner: str, repo: str) -> Repository:
    """
    Get a PyGithub Repository object.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :return: A PyGithub Repository object.
    """
    return github.get_repo(f"{owner}/{repo}")


def compare_shas(owner: str, repo: str, base: str, head: str) -> List[Commit]:
    """
    Compare two SHAs and return the list of commits between them.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param base: The base SHA.
    :param head: The head SHA.
    :return: A list of PyGithub Commit objects.
    """
    repository: Repository = get_repo(owner, repo)
    comparison = repository.compare(base, head)
    return [commit for commit in comparison.commits]


def get_all_commits(owner: str, repo: str, params: Optional[Dict[str, Any]] = None) -> List[Commit]:
    """
    Fetch all commits for a given repository.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param params: Optional parameters for filtering (e.g., 'since', 'sha', 'number').
    :return: A list of PyGithub Commit objects.
    """
    repository: Repository = get_repo(owner, repo)
    gh_options: Dict[str, Any] = {}
    if params:
        if "since" in params:
            gh_options["since"] = params["since"]
        if "sha" in params:
            gh_options["sha"] = params["sha"]

    commits: PaginatedList[Commit] = repository.get_commits(**gh_options)
    if params and "number" in params:
        return [commit for commit in commits[: params["number"]]]
    return [commit for commit in commits]


def get_commit(owner: str, repo: str, sha: str) -> Commit:
    """
    Fetch a specific commit by its SHA.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param sha: The commit SHA.
    :return: A PyGithub Commit object.
    """
    repository: Repository = get_repo(owner, repo)
    return repository.get_commit(sha)


def get_pull_request(owner: str, repo: str, pr_id: int) -> PullRequest:
    """
    Fetch a specific pull request by its ID.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param pr_id: The pull request number.
    :return: A PyGithub PullRequest object.
    """
    repository: Repository = get_repo(owner, repo)
    return repository.get_pull(pr_id)


def get_pull_request_commits(owner: str, repo: str, pr_id: int) -> List[Commit]:
    """
    Fetch the list of commits for a given pull request.

    :param owner: The owner of the repository.
    :param repo: The name of the repository.
    :param pr_id: The pull request number.
    :return: A list of PyGithub Commit objects.
    """
    pr: PullRequest = get_pull_request(owner, repo, pr_id)
    return [commit for commit in pr.get_commits()]
