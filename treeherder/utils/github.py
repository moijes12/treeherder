from github import Auth, Github

from treeherder.config.settings import GITHUB_TOKEN

if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github = Github(auth=auth)
else:
    github = Github()


def get_releases(owner, repo, params=None):
    repository = get_repo(owner, repo)
    releases = repository.get_releases()

    # Apply filtering by date if 'since' is provided in params
    if params and "since" in params:
        since = params["since"]
        if isinstance(since, str):
            from dateutil.parser import parse

            since_dt = parse(since)
        else:
            since_dt = since

        # Filtering releases where published_at > since
        releases = [r for r in releases if r.published_at and r.published_at > since_dt]

    if params and "number" in params:
        # Replicating the old behavior where params['number'] limited the results
        return [release.raw_data for release in releases[: params["number"]]]
    return [release.raw_data for release in releases]


def get_repo(owner, repo):
    return github.get_repo(f"{owner}/{repo}")


def compare_shas(owner, repo, base, head):
    repository = get_repo(owner, repo)
    comparison = repository.compare(base, head)
    return [commit for commit in comparison.commits]


def get_all_commits(owner, repo, params=None):
    repository = get_repo(owner, repo)
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


def get_commit(owner, repo, sha):
    repository = get_repo(owner, repo)
    return repository.get_commit(sha).raw_data


def get_pull_request(owner, repo, pr_id):
    repository = get_repo(owner, repo)
    return repository.get_pull(pr_id)


def get_pull_request_commits(owner, repo, pr_id):
    pr = get_pull_request(owner, repo, pr_id)
    return [commit for commit in pr.get_commits()]
