import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable, Optional

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


@dataclass
class GitAuthorCommitter:
    name: Optional[str] = None
    email: Optional[str] = None
    date: Optional[Any] = None

    @classmethod
    def from_obj(cls, obj: Any) -> Optional["GitAuthorCommitter"]:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return cls(
                name=obj.get("name"),
                email=obj.get("email"),
                date=obj.get("date"),
            )
        return cls(
            name=getattr(obj, "name", None),
            email=getattr(obj, "email", None),
            date=getattr(obj, "date", None),
        )


@dataclass
class InnerGitCommit:
    message: Optional[str] = None
    author: Optional[GitAuthorCommitter] = None
    committer: Optional[GitAuthorCommitter] = None

    @classmethod
    def from_obj(cls, obj: Any) -> Optional["InnerGitCommit"]:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return cls(
                message=obj.get("message"),
                author=GitAuthorCommitter.from_obj(obj.get("author")),
                committer=GitAuthorCommitter.from_obj(obj.get("committer")),
            )
        return cls(
            message=getattr(obj, "message", None),
            author=GitAuthorCommitter.from_obj(getattr(obj, "author", None)),
            committer=GitAuthorCommitter.from_obj(getattr(obj, "committer", None)),
        )


@dataclass
class CommitParent:
    sha: Optional[str] = None
    url: Optional[str] = None

    @classmethod
    def from_obj(cls, obj: Any) -> Optional["CommitParent"]:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return cls(
                sha=obj.get("sha"),
                url=obj.get("url"),
            )
        return cls(
            sha=getattr(obj, "sha", None),
            url=getattr(obj, "url", None),
        )


@dataclass
class CommitData:
    sha: Optional[str] = None
    commit: Optional[InnerGitCommit] = None
    parents: list[CommitParent] = field(default_factory=list)

    @classmethod
    def from_obj(cls, obj: Any) -> Optional["CommitData"]:
        if obj is None:
            return None
        if isinstance(obj, dict):
            parents = [
                p_obj
                for p in obj.get("parents", [])
                if (p_obj := CommitParent.from_obj(p)) is not None
            ]
            return cls(
                sha=obj.get("sha"),
                commit=InnerGitCommit.from_obj(obj.get("commit")),
                parents=parents,
            )
        raw_parents = getattr(obj, "parents", None) or []
        parents = [
            p_obj
            for p in raw_parents
            if (p_obj := CommitParent.from_obj(p)) is not None
        ]
        return cls(
            sha=getattr(obj, "sha", None),
            commit=InnerGitCommit.from_obj(getattr(obj, "commit", None)),
            parents=parents,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonData:
    merge_base_commit: Optional[CommitData] = None

    @classmethod
    def from_obj(cls, obj: Any) -> "ComparisonData":
        if isinstance(obj, dict):
            mb = obj.get("merge_base_commit")
        else:
            mb = getattr(obj, "merge_base_commit", None)
        return cls(merge_base_commit=CommitData.from_obj(mb))

    def to_dict(self, raw_commits: Optional[Iterable[Any]] = None) -> dict[str, Any]:
        mb_dict = asdict(self.merge_base_commit) if self.merge_base_commit else None
        commits_src = raw_commits if raw_commits is not None else []
        commits_gen = (
            cd.to_dict()
            for c in commits_src
            if (cd := CommitData.from_obj(c)) is not None
        )
        return {
            "merge_base_commit": mb_dict,
            "commits": commits_gen,
        }

    def to_json(self, raw_commits: Optional[Iterable[Any]] = None) -> str:
        d = self.to_dict(raw_commits=raw_commits)
        if "commits" in d and not isinstance(d["commits"], list):
            d["commits"] = list(d["commits"])
        return json.dumps(d, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "ComparisonData":
        data = json.loads(json_str)
        return cls.from_obj(data)


def compare_shas(owner, repo, base, head, get_comparison_object=False):
    repo = pygithub_get_repo(owner, repo)
    comparison = repo.compare(base, head)
    if get_comparison_object:
        comp_data = ComparisonData.from_obj(comparison)
        raw_commits = getattr(comparison, "commits", None)
        if isinstance(comparison, dict):
            raw_commits = comparison.get("commits")
        return comp_data.to_dict(raw_commits=raw_commits)
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
