from datetime import UTC, datetime

from github import Auth, Github
from github.GitRelease import GitRelease

from treeherder.config.settings import GITHUB_TOKEN

if GITHUB_TOKEN:
    auth = Auth.Token(GITHUB_TOKEN)
    github = Github(auth=auth)
else:
    github = Github()


def pygithub_get_repo(owner, repo):
    return github.get_repo(f"{owner}/{repo}")


def get_releases(owner, repo, params=None):
    """
    Retrieve GitHub releases for a given repository.
    Returns a list of standardized dictionaries representing releases.
    """
    paginated_releases = pygithub_get_repo(owner=owner, repo=repo).get_releases()

    releases: list[GitRelease] = []
    since_dt = None
    max_number = None

    if params:
        max_number = params.get("number")
        since_dt = params.get("since", None)
        if since_dt:
            since_dt = datetime.fromisoformat(since_dt)
            if since_dt.tzinfo is None:
                since_dt.replace(tzinfo=UTC)

    for release in paginated_releases:
        # Break if we have reached max_number
        if max_number and len(releases) >= max_number:
            break

        # PyGithub returns releases in reverse chronological order
        # Stop immediately if releases older than the since_dt are found
        release_dt = release.published_at
        if since_dt and release_dt:
            if release_dt.tzinfo is None:
                release_dt.replace(tzinfo=UTC)
            if release.published_at < since_dt:
                break
        release_dict = {
            "id": release.id,
            "name": release.name,
            "tag_name": release.tag_name,
            "published_at": release.published_at,
            "html_url": release.html_url,
            "author": {"login": release.author.login if release.author else "unknown"},
        }
        releases.append(release_dict)

    return releases


def _user_to_dict(user):
    if user is None:
        return None
    if isinstance(user, dict):
        return user
    d = {}
    if hasattr(user, "login"):
        d["login"] = user.login
    if hasattr(user, "id"):
        d["id"] = user.id
    if hasattr(user, "avatar_url"):
        d["avatar_url"] = user.avatar_url
    if hasattr(user, "html_url"):
        d["html_url"] = user.html_url
    if hasattr(user, "type"):
        d["type"] = user.type
    return d if d else str(user)


def _git_author_committer_to_dict(ac):
    if ac is None:
        return None
    if isinstance(ac, dict):
        return ac
    d = {}
    if hasattr(ac, "name"):
        d["name"] = ac.name
    if hasattr(ac, "email"):
        d["email"] = ac.email
    if hasattr(ac, "date"):
        d["date"] = ac.date
    return d


def _inner_git_commit_to_dict(git_commit):
    if git_commit is None:
        return None
    if isinstance(git_commit, dict):
        return git_commit
    d = {}
    if hasattr(git_commit, "message"):
        d["message"] = git_commit.message
    if hasattr(git_commit, "author"):
        d["author"] = _git_author_committer_to_dict(git_commit.author)
    if hasattr(git_commit, "committer"):
        d["committer"] = _git_author_committer_to_dict(git_commit.committer)
    if hasattr(git_commit, "tree") and git_commit.tree:
        tree = git_commit.tree
        d["tree"] = (
            tree
            if isinstance(tree, dict)
            else {
                "sha": getattr(tree, "sha", None),
                "url": getattr(tree, "url", None),
            }
        )
    if hasattr(git_commit, "comment_count"):
        d["comment_count"] = git_commit.comment_count
    if hasattr(git_commit, "verification") and git_commit.verification:
        v = git_commit.verification
        d["verification"] = (
            v
            if isinstance(v, dict)
            else {
                "verified": getattr(v, "verified", None),
                "reason": getattr(v, "reason", None),
            }
        )
    if hasattr(git_commit, "url"):
        d["url"] = git_commit.url
    return d


def _parent_to_dict(parent):
    if parent is None:
        return None
    if isinstance(parent, dict):
        return parent
    d = {}
    if hasattr(parent, "sha"):
        d["sha"] = parent.sha
    if hasattr(parent, "url"):
        d["url"] = parent.url
    if hasattr(parent, "html_url"):
        d["html_url"] = parent.html_url
    return d


def _file_to_dict(file_obj):
    if file_obj is None:
        return None
    if isinstance(file_obj, dict):
        return file_obj
    d = {}
    for attr in (
        "filename",
        "additions",
        "deletions",
        "changes",
        "status",
        "raw_url",
        "blob_url",
        "patch",
        "sha",
    ):
        if hasattr(file_obj, attr):
            d[attr] = getattr(file_obj, attr)
    return d


def _commit_to_dict(commit):
    if commit is None:
        return None
    if isinstance(commit, dict):
        return commit
    d = {}
    if hasattr(commit, "sha"):
        d["sha"] = commit.sha
    if hasattr(commit, "node_id"):
        d["node_id"] = commit.node_id
    if hasattr(commit, "commit"):
        d["commit"] = _inner_git_commit_to_dict(commit.commit)
    if hasattr(commit, "author"):
        d["author"] = _user_to_dict(commit.author)
    if hasattr(commit, "committer"):
        d["committer"] = _user_to_dict(commit.committer)
    if hasattr(commit, "parents") and commit.parents is not None:
        d["parents"] = [_parent_to_dict(p) for p in commit.parents]
    if hasattr(commit, "files") and commit.files is not None:
        d["files"] = [_file_to_dict(f) for f in commit.files]
    if hasattr(commit, "stats") and commit.stats is not None:
        st = commit.stats
        d["stats"] = (
            st
            if isinstance(st, dict)
            else {
                "additions": getattr(st, "additions", None),
                "deletions": getattr(st, "deletions", None),
                "total": getattr(st, "total", None),
            }
        )
    if hasattr(commit, "url"):
        d["url"] = commit.url
    if hasattr(commit, "html_url"):
        d["html_url"] = commit.html_url
    if hasattr(commit, "comments_url"):
        d["comments_url"] = commit.comments_url
    return d


def _comparison_to_dict(comparison):
    if isinstance(comparison, dict):
        return comparison

    d = {}
    if hasattr(comparison, "url"):
        d["url"] = comparison.url
    if hasattr(comparison, "html_url"):
        d["html_url"] = comparison.html_url
    if hasattr(comparison, "permalink_url"):
        d["permalink_url"] = comparison.permalink_url
    if hasattr(comparison, "diff_url"):
        d["diff_url"] = comparison.diff_url
    if hasattr(comparison, "patch_url"):
        d["patch_url"] = comparison.patch_url
    if hasattr(comparison, "base_commit") and comparison.base_commit is not None:
        d["base_commit"] = _commit_to_dict(comparison.base_commit)
    if hasattr(comparison, "merge_base_commit") and comparison.merge_base_commit is not None:
        d["merge_base_commit"] = _commit_to_dict(comparison.merge_base_commit)
    if hasattr(comparison, "status"):
        d["status"] = comparison.status
    if hasattr(comparison, "ahead_by"):
        d["ahead_by"] = comparison.ahead_by
    if hasattr(comparison, "behind_by"):
        d["behind_by"] = comparison.behind_by
    if hasattr(comparison, "total_commits"):
        d["total_commits"] = comparison.total_commits
    if hasattr(comparison, "commits") and comparison.commits is not None:
        d["commits"] = (_commit_to_dict(c) for c in comparison.commits)
    if hasattr(comparison, "files") and comparison.files is not None:
        d["files"] = (_file_to_dict(f) for f in comparison.files)
    return d


def compare_shas(owner, repo, base, head, get_comparison_object=False):
    repo = pygithub_get_repo(owner, repo)
    comparison = repo.compare(base, head)
    if get_comparison_object:
        return _comparison_to_dict(comparison)
    return [commit for commit in comparison.commits]


def get_all_commits(owner, repo, params=None):
    repo_obj = pygithub_get_repo(owner, repo)
    return [{"sha": commit.sha} for commit in repo_obj.get_commits()]


def get_commit(owner, repo, sha, params=None):
    """
    Retrieve GitHub commit for a given sha.
    Returns a standardized dictionary representing a commit.
    """
    repo_object = pygithub_get_repo(owner, repo)
    commit = repo_object.get_commit(sha)
    commit_dict = {}

    # Append file objects required by collector.py
    commit_dict["files"] = []
    for file in commit.files:
        f = {}
        f["filename"] = file.filename
        commit_dict["files"].append(f)

    # Append object required by ingest.py
    commit_dict["commit"] = {"committer": {"date": commit.commit.committer.date}}
    commit_dict["parents"] = []
    for parent in commit.parents:
        commit_dict["parents"].append({"sha": parent.sha})
    return commit_dict


def get_pull_request(owner, repo, pr_id):
    repo = pygithub_get_repo(owner, repo)
    return repo.get_pull(pr_id)


def get_pull_request_commits(owner, repo, pr_id):
    pr = get_pull_request(owner, repo, pr_id)
    return [commit for commit in pr.get_commits()]
