from github import Auth, Github

from treeherder.config.settings import GITHUB_TOKEN

if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github_client = Github(auth=auth)
else:
    github_client = Github()


def get_github_repo(owner, repo_name):
    """
    Returns a PyGithub Repository object.
    """
    return github_client.get_repo(f"{owner}/{repo_name}")


def get_releases(owner, repo_name):
    """
    Returns a PaginatedList of PyGithub Release objects.
    """
    repo = get_github_repo(owner, repo_name)
    return repo.get_releases()


def compare_shas(owner, repo_name, base, head):
    """
    Returns a PyGithub CommitComparison object.
    """
    repo = get_github_repo(owner, repo_name)
    return repo.compare(base, head)


def get_all_commits(owner, repo_name, params=None):
    """
    Returns a PaginatedList of PyGithub Commit objects.
    Optional params: sha, since, until, path, author, committer, per_page.
    """
    repo = get_github_repo(owner, repo_name)
    return repo.get_commits(**(params or {}))


def get_commit(owner, repo_name, sha):
    """
    Returns a PyGithub Commit object.
    """
    repo = get_github_repo(owner, repo_name)
    return repo.get_commit(sha)


def get_pull_request(owner, repo_name, pr_id):
    """
    Returns a PyGithub PullRequest object.
    """
    repo = get_github_repo(owner, repo_name)
    return repo.get_pull(pr_id)


def get_pull_request_commits(owner, repo_name, pr_id):
    """
    Returns a PaginatedList of PyGithub Commit objects associated with a PR.
    """
    pr = get_pull_request(owner, repo_name, pr_id)
    return pr.get_commits()
