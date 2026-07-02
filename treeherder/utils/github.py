from github import Auth, Github

from treeherder.config.settings import GITHUB_TOKEN

if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github = Github(auth=auth)
else:
    github = Github()


def get_releases(owner, repo):
    repo = pygithub_get_repo(owner, repo)
    return repo.get_releases()


def get_repo(owner, repo):
    return pygithub_get_repo(owner, repo)


def pygithub_get_repo(owner, repo):
    return github.get_repo(f"{owner}/{repo}")


def compare_shas(owner, repo, base, head):
    repo = pygithub_get_repo(owner, repo)
    comparison = repo.compare(base, head)
    return [commit for commit in comparison.commits]


def get_all_commits(owner, repo, params=None):
    repo = pygithub_get_repo(owner, repo)
    if params:
        return repo.get_commits(**params)
    return repo.get_commits()


def get_commit(owner, repo, sha):
    repo = pygithub_get_repo(owner, repo)
    return repo.get_commit(sha)


def get_pull_request(owner, repo, pr_id):
    repo = pygithub_get_repo(owner, repo)
    return repo.get_pull(pr_id)


def get_pull_request_commits(owner, repo, pr_id):
    pr = get_pull_request(owner, repo, pr_id)
    return [commit for commit in pr.get_commits()]
