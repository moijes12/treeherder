import copy
import datetime
import json
import os

import pytest
from github import GithubException
from github.Commit import Commit
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from github.Repository import Repository
from responses import RequestsMock

from treeherder.etl.push_loader import (
    GithubPullRequestTransformer,
    GithubPushTransformer,
    HgPushFetchError,
    HgPushTransformer,
    PulsePushError,
    PushLoader,
)
from treeherder.model.models import Push, RepositoryBranch


# --- PyGithub Mock Objects ---
class MockPaginatedList(PaginatedList):
    def __init__(self, data):
        self._data = data
        self._requester = None  # Not used in our mocks

    def __iter__(self):
        yield from self._data

    def get_page(self, page_no):
        start = (page_no - 1) * 30  # Default per_page for PyGithub is 30
        end = start + 30
        return self._data[start:end]


class MockCommit(Commit):
    def __init__(self, sha, message, author, committer, parents=None):
        self._sha = sha
        self._message = message
        self._author_data = author
        self._committer_data = committer
        self._parents_data = parents or []

    @property
    def sha(self):
        return self._sha

    @property
    def commit(self):
        # Mimic github.GitCommit.GitCommit object
        return type(
            "GitCommit",
            (object,),
            {
                "message": self._message,
                "author": type(
                    "GitAuthor", (object,), self._author_data if self._author_data else {}
                )(),
                "committer": type(
                    "GitCommitter", (object,), self._committer_data if self._committer_data else {}
                )(),
            },
        )()

    @property
    def parents(self):
        # Returns a list of MockCommit objects for parents
        return [MockCommit(parent_sha, "", None, None) for parent_sha in self._parents_data]


class MockCommitComparison:
    def __init__(self, base_sha, head_sha, commits, merge_base_commit_sha=None):
        self._base_sha = base_sha
        self._head_sha = head_sha
        self._commits = commits
        self._merge_base_commit_sha = merge_base_commit_sha

    @property
    def merge_base_commit(self):
        if self._merge_base_commit_sha:
            return MockCommit(
                self._merge_base_commit_sha,
                "Merge base commit",
                {"date": datetime.datetime.now().isoformat()},
                {"date": datetime.datetime.now().isoformat()},
                parents=[],
            )
        return None

    @property
    def commits(self):
        return self._commits


class MockPullRequest(PullRequest):
    def __init__(self, number, base_repo_url, head_repo_url, base_sha, head_sha, commits):
        self._number = number
        self._base_repo_url = base_repo_url
        self._head_repo_url = head_repo_url
        self._base_sha = base_sha
        self._head_sha = head_sha
        self._commits = commits

    @property
    def number(self):
        return self._number

    @property
    def base(self):
        return type(
            "PullRequestBranch",
            (object,),
            {
                "repo": type("Repository", (object,), {"clone_url": self._base_repo_url})(),
                "sha": self._base_sha,
            },
        )()

    @property
    def head(self):
        return type(
            "PullRequestBranch",
            (object,),
            {
                "repo": type("Repository", (object,), {"clone_url": self._head_repo_url})(),
                "sha": self._head_sha,
            },
        )()

    def get_commits(self):
        return MockPaginatedList(self._commits)


class MockRepository(Repository):
    def __init__(self, owner, name, pulls=None, commits=None, comparisions=None):
        self._owner = owner
        self._name = name
        self._pulls = pulls or {}
        self._commits = commits or {}
        self._comparisions = comparisions or {}

    def get_pull(self, pr_id):
        return self._pulls.get(pr_id)

    def compare(self, base, head):
        return self._comparisions.get((base, head))

    def get_commit(self, sha):
        return self._commits.get(sha)

    def get_commits(self, **kwargs):
        # Basic mock for get_commits, can be enhanced for filters
        return MockPaginatedList(list(self._commits.values()))


@pytest.fixture
def github_push(sample_data):
    return copy.deepcopy(sample_data.github_push)


@pytest.fixture
def github_pr(sample_data):
    return copy.deepcopy(sample_data.github_pr)


@pytest.fixture
def hg_push(sample_data):
    return copy.deepcopy(sample_data.hg_push)


@pytest.fixture
def transformed_github_push(sample_data):
    return copy.deepcopy(sample_data.transformed_github_push)


@pytest.fixture
def transformed_github_pr(sample_data):
    return copy.deepcopy(sample_data.transformed_github_pr)


@pytest.fixture
def transformed_hg_push(sample_data):
    return copy.deepcopy(sample_data.transformed_hg_push)


@pytest.fixture
def mock_github_pr_commits(monkeypatch):
    """Mocks PyGithub calls for fetching PR data and commits."""
    # Load sample commit data
    tests_folder = os.path.dirname(os.path.dirname(__file__))
    pr_commits_path = os.path.join(
        tests_folder, "sample_data/pulse_consumer", "github_pr_commits.json"
    )
    with open(pr_commits_path) as f:
        raw_commits = json.load(f)

    # Convert raw commit data to MockCommit objects
    mock_commits = []
    for commit_data in raw_commits:
        mock_commits.append(
            MockCommit(
                sha=commit_data["sha"],
                message=commit_data["commit"]["message"],
                author={
                    "name": commit_data["commit"]["author"]["name"],
                    "email": commit_data["commit"]["author"]["email"],
                    "date": commit_data["commit"]["author"]["date"],
                },
                committer={
                    "name": commit_data["commit"]["committer"]["name"],
                    "email": commit_data["commit"]["committer"]["email"],
                    "date": commit_data["commit"]["committer"]["date"],
                },
                parents=[p["sha"] for p in commit_data["parents"]],
            )
        )

    mock_pr = MockPullRequest(
        number=1692,
        base_repo_url="https://github.com/mozilla/test_treeherder.git",
        head_repo_url="https://github.com/mozilla/test_treeherder.git",
        base_sha="d8b7b2b0a3f4e5c6d7e8f9a0b1c2d3e4f5a6b7c8",
        head_sha="0f1e2d3c4b5a69788796a5b4c3d2e1f0e9d8c7b6",
        commits=mock_commits,
    )

    mock_repo = MockRepository(
        owner="mozilla",
        name="test_treeherder",
        pulls={1692: mock_pr},
    )

    monkeypatch.setattr(
        "treeherder.utils.github.github_client.get_repo", lambda fullname: mock_repo
    )


@pytest.fixture
def mock_github_push_compare(monkeypatch, activate_responses):
    """Mocks PyGithub calls for fetching push comparison and commit data, and also keeps original
    responses for hg.mozilla.org (which are used by GithubPushTransformer internally for Hg related stuff)."""

    # Keep original responses for hg.mozilla.org in case activate_responses is used
    # in conjunction with this fixture for other non-PyGithub related mocks.
    # This is important because the GithubPushTransformer might still use fetch_json for certain cases,
    # or the test setup might have other HTTP requests.
    if isinstance(activate_responses, RequestsMock):
        # Load sample data for github_repository_android-components.json
        tests_folder = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(
            tests_folder, "sample_data/pulse_consumer", "github_repository_android-components.json"
        )
        with open(path) as f:
            mocked_content = json.load(f)
        activate_responses.add(
            RequestsMock.GET,
            "https://api.github.com:443/repos/mozilla-mobile/android-components",
            json=mocked_content,
            status=200,
            content_type="application/json",
        )

        path = os.path.join(
            tests_folder, "sample_data/pulse_consumer", "github_repository_servo.json"
        )
        with open(path) as f:
            mocked_content = json.load(f)
        activate_responses.add(
            RequestsMock.GET,
            "https://api.github.com:443/repos/servo/servo",
            json=mocked_content,
            status=200,
            content_type="application/json",
        )

        path = os.path.join(tests_folder, "sample_data/pulse_consumer", "github_push_compare.json")
        with open(path) as f:
            mocked_content = json.load(f)
        activate_responses.add(
            RequestsMock.GET,
            "https://api.github.com:443/repos/mozilla-mobile/android-components/compare/"
            "7285afe57ae6207fdb5d6db45133dac2053b7820..."
            "5fdb785b28b356f50fc1d9cb180d401bb03fc1f1",
            json=mocked_content[0],
            status=200,
            content_type="application/json",
        )
        activate_responses.add(
            RequestsMock.GET,
            "https://api.github.com:443/repos/servo/servo/compare/"
            "4c25e02f26f7536edbf23a360d56604fb9507378..."
            "ad9bfc2a62b70b9f3dbb1c3a5969f30bacce3d74",
            json=mocked_content[1],
            status=200,
            content_type="application/json",
        )

    # PyGithub mock for compare and get_commit
    # Mock for mozilla-mobile/android-components
    android_commits_data = [
        {
            "sha": "5fdb785b28b356f50fc1d9cb180d401bb03fc1f1",
            "commit": {
                "message": "Update build.gradle",
                "author": {
                    "name": "Author One",
                    "email": "author1@example.com",
                    "date": "2023-01-01T12:00:00Z",
                },
                "committer": {
                    "name": "Committer One",
                    "email": "committer1@example.com",
                    "date": "2023-01-01T12:00:00Z",
                },
            },
            "parents": [{"sha": "7285afe57ae6207fdb5d6db45133dac2053b7820"}],
        }
    ]
    android_mock_commits = [
        MockCommit(
            sha=c["sha"],
            message=c["commit"]["message"],
            author=c["commit"]["author"],
            committer=c["commit"]["committer"],
            parents=[p["sha"] for p in c["parents"]],
        )
        for c in android_commits_data
    ]
    android_mock_compare = MockCommitComparison(
        base_sha="7285afe57ae6207fdb5d6db45133dac2053b7820",
        head_sha="5fdb785b28b356f50fc1d9cb180d401bb03fc1f1",
        commits=android_mock_commits,
        merge_base_commit_sha="7285afe57ae6207fdb5d6db45133dac2053b7820",
    )

    # Mock for servo/servo
    servo_commits_data = [
        {
            "sha": "ad9bfc2a62b70b9f3dbb1c3a5969f30bacce3d74",
            "commit": {
                "message": "Another commit",
                "author": {
                    "name": "Author Two",
                    "email": "author2@example.com",
                    "date": "2023-01-02T12:00:00Z",
                },
                "committer": {
                    "name": "Committer Two",
                    "email": "committer2@example.com",
                    "date": "2023-01-02T12:00:00Z",
                },
            },
            "parents": [{"sha": "4c25e02f26f7536edbf23a360d56604fb9507378"}],
        }
    ]
    servo_mock_commits = [
        MockCommit(
            sha=c["sha"],
            message=c["commit"]["message"],
            author=c["commit"]["author"],
            committer=c["commit"]["committer"],
            parents=[p["sha"] for p in c["parents"]],
        )
        for c in servo_commits_data
    ]
    servo_mock_compare = MockCommitComparison(
        base_sha="4c25e02f26f7536edbf23a360d56604fb9507378",
        head_sha="ad9bfc2a62b70b9f3dbb1c3a5969f30bacce3d74",
        commits=servo_mock_commits,
        merge_base_commit_sha="4c25e02f26f7536edbf23a360d56604fb9507378",
    )

    def mock_get_repo(fullname):
        if fullname == "mozilla-mobile/android-components":
            return MockRepository(
                owner="mozilla-mobile",
                name="android-components",
                comparisions={
                    (
                        "7285afe57ae6207fdb5d6db45133dac2053b7820",
                        "5fdb785b28b356f50fc1d9cb180d401bb03fc1f1",
                    ): android_mock_compare
                },
                commits={
                    "5fdb785b28b356f50fc1d9cb180d401bb03fc1f1": android_mock_commits[0],
                    "7285afe57ae6207fdb5d6db45133dac2053b7820": MockCommit(
                        "7285afe57ae6207fdb5d6db45133dac2053b7820", "Base commit", {}, {}
                    ),
                },
            )
        elif fullname == "servo/servo":
            return MockRepository(
                owner="servo",
                name="servo",
                comparisions={
                    (
                        "4c25e02f26f7536edbf23a360d56604fb9507378",
                        "ad9bfc2a62b70b9f3dbb1c3a5969f30bacce3d74",
                    ): servo_mock_compare
                },
                commits={
                    "ad9bfc2a62b70b9f3dbb1c3a5969f30bacce3d74": servo_mock_commits[0],
                    "4c25e02f26f7536edbf23a360d56604fb9507378": MockCommit(
                        "4c25e02f26f7536edbf23a360d56604fb9507378", "Base commit", {}, {}
                    ),
                },
            )
        raise GithubException(status=404, data={"message": "Not Found"})

    monkeypatch.setattr("treeherder.utils.github.github_client.get_repo", mock_get_repo)


@pytest.fixture
def mock_hg_push_commits(activate_responses: RequestsMock):
    tests_folder = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(tests_folder, "sample_data/pulse_consumer", "hg_push_commits.json")
    with open(path) as f:
        mocked_content = f.read()
    activate_responses.add(
        RequestsMock.GET,
        "https://hg.mozilla.org/try/json-pushes",
        body=mocked_content,
        status=200,
        content_type="application/json",
    )


@pytest.mark.parametrize(
    "exchange, transformer_class",
    [
        ("exchange/taskcluster-github/v1/push", GithubPushTransformer),
        ("exchange/taskcluster-github/v1/pull-request", GithubPullRequestTransformer),
    ],
)
def test_get_transformer_class(exchange, transformer_class):
    rsl = PushLoader()
    assert rsl.get_transformer_class(exchange) == transformer_class


def test_unsupported_exchange():
    with pytest.raises(PulsePushError):
        rsl = PushLoader()
        rsl.get_transformer_class("meh")


def test_ingest_github_pull_request(
    test_repository, github_pr, transformed_github_pr, mock_github_pr_commits
):
    xformer = GithubPullRequestTransformer(github_pr)
    push = xformer.transform(test_repository.name)
    assert transformed_github_pr == push


def test_ingest_github_push(
    test_repository, github_push, transformed_github_push, mock_github_push_compare
):
    xformer = GithubPushTransformer(github_push[0]["payload"])
    push = xformer.transform(test_repository.name)
    assert transformed_github_push == push


def test_ingest_github_push_new_branch(github_push):
    """Webhook body commits are used when base SHA is all zeroes (new branch)."""
    github_push[0]["payload"]["details"]["event.base.sha"] = "0" * 40
    commits = github_push[0]["payload"]["body"]["commits"]

    xformer = GithubPushTransformer(github_push[0]["payload"])
    push = xformer.transform("some-repo")

    assert push["revision"] == commits[-1]["id"]
    assert len(push["revisions"]) == len(commits)


def test_ingest_hg_push(test_repository, hg_push, transformed_hg_push, mock_hg_push_commits):
    xformer = HgPushTransformer(hg_push)
    push = xformer.transform(test_repository.name)
    assert transformed_hg_push == push


@pytest.mark.django_db
def test_ingest_hg_push_good_repo(hg_push, test_repository, mock_hg_push_commits):
    """Test graceful handling of an unknown HG repo"""
    hg_push["payload"]["repo_url"] = "https://hg.mozilla.org/mozilla-central"
    assert Push.objects.count() == 0
    PushLoader().process(
        hg_push, "exchange/hgpushes/v1", "https://firefox-ci-tc.services.mozilla.com"
    )
    assert Push.objects.count() == 1


@pytest.mark.django_db
def test_ingest_hg_push_bad_repo(hg_push):
    """Test graceful handling of an unknown HG repo"""
    hg_push["payload"]["repo_url"] = "https://bad.repo.com"
    PushLoader().process(
        hg_push, "exchange/hgpushes/v1", "https://firefox-ci-tc.services.mozilla.com"
    )
    assert Push.objects.count() == 0


@pytest.mark.django_db
def test_ingest_hg_push_ignores_wildcard_repo(hg_push, test_repository, mock_hg_push_commits):
    """Repos with wildcard branches are not matched for Hg pushes"""
    from treeherder.model.models import Repository

    hg_push["payload"]["repo_url"] = test_repository.url
    wildcard_repo = Repository.objects.create(
        name="wildcard-hg",
        repository_group=test_repository.repository_group,
        dvcs_type="hg",
        url=test_repository.url,
        tc_root_url=test_repository.tc_root_url,
    )
    RepositoryBranch.objects.create(repository=wildcard_repo, branch="*")
    PushLoader().process(
        hg_push, "exchange/hgpushes/v1", "https://firefox-ci-tc.services.mozilla.com"
    )
    assert Push.objects.count() == 1
    assert Push.objects.first().repository == test_repository


@pytest.mark.django_db
def test_ingest_github_push_bad_repo(github_push):
    """Test graceful handling of an unknown GH repo"""
    github_push[0]["payload"]["details"]["event.head.repo.url"] = "https://bad.repo.com"
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 0


@pytest.mark.django_db
def test_ingest_github_push_merge_commit(github_push, test_repository, mock_github_push_compare):
    """Test a a merge push which will require hitting the network for the right info"""
    test_repository.url = github_push[1]["payload"]["details"]["event.head.repo.url"].replace(
        ".git", ""
    )
    test_repository.save()
    RepositoryBranch.objects.create(
        repository=test_repository,
        branch=github_push[1]["payload"]["details"]["event.base.repo.branch"],
    )
    PushLoader().process(
        github_push[1]["payload"],
        github_push[1]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "branch, expected_pushes",
    [
        ("master", 1),
        ("bar", 1),
        ("baz", 0),
        ("foo", 1),
    ],
)
def test_ingest_github_push_comma_separated_branches(
    branch, expected_pushes, github_push, test_repository, mock_github_push_compare
):
    """Test a repository accepting pushes for multiple explicitly-listed branches"""
    test_repository.url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(
        ".git", ""
    )
    test_repository.save()
    for b in ["master", "foo", "bar"]:
        RepositoryBranch.objects.create(repository=test_repository, branch=b)
    github_push[0]["payload"]["details"]["event.base.repo.branch"] = branch
    assert Push.objects.count() == 0
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == expected_pushes


@pytest.mark.django_db
def test_ingest_github_push_wildcard_repo(github_push, test_repository, mock_github_push_compare):
    """Repo with branch='*' accepts a push on any branch"""
    test_repository.url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(
        ".git", ""
    )
    test_repository.save()
    RepositoryBranch.objects.create(repository=test_repository, branch="*")
    github_push[0]["payload"]["details"]["event.base.repo.branch"] = "my-feature-branch"
    assert Push.objects.count() == 0
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 1


@pytest.mark.django_db
def test_ingest_github_push_explicit_beats_wildcard(
    github_push, test_repository, mock_github_push_compare
):
    """Explicit branch match takes precedence over wildcard for the same URL"""
    from treeherder.model.models import Repository

    url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(".git", "")
    branch = github_push[0]["payload"]["details"]["event.base.repo.branch"]

    test_repository.url = url
    test_repository.save()
    RepositoryBranch.objects.create(repository=test_repository, branch=branch)

    wildcard_repo = Repository.objects.create(
        name="wildcard-repo",
        repository_group=test_repository.repository_group,
        dvcs_type="git",
        url=url,
        tc_root_url=test_repository.tc_root_url,
    )
    RepositoryBranch.objects.create(repository=wildcard_repo, branch="*")

    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 1
    push = Push.objects.first()
    assert push.repository == test_repository
    assert push.repository != wildcard_repo


@pytest.mark.django_db
def test_ingest_github_push_special_char_branch(
    github_push, test_repository, mock_github_push_compare
):
    """Branch names with special chars are handled safely via wildcard branch record"""
    test_repository.url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(
        ".git", ""
    )
    test_repository.save()
    RepositoryBranch.objects.create(repository=test_repository, branch="*")
    github_push[0]["payload"]["details"]["event.base.repo.branch"] = "release/v1.2+hotfix"
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "branch, expected_pushes",
    [
        ("releases/v1.2", 1),
        ("master", 0),
    ],
)
def test_ingest_github_push_prefix_wildcard(
    branch, expected_pushes, github_push, test_repository, mock_github_push_compare
):
    """A prefix wildcard like 'releases/*' matches branches under that prefix only"""
    test_repository.url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(
        ".git", ""
    )
    test_repository.save()
    RepositoryBranch.objects.create(repository=test_repository, branch="releases/*")
    github_push[0]["payload"]["details"]["event.base.repo.branch"] = branch
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == expected_pushes


@pytest.mark.django_db
def test_ingest_github_push_ambiguous_wildcards_skipped(
    github_push, test_repository, mock_github_push_compare
):
    """When two wildcard patterns both match, the push is skipped"""
    from treeherder.model.models import Repository

    url = github_push[0]["payload"]["details"]["event.head.repo.url"].replace(".git", "")
    test_repository.url = url
    test_repository.save()
    RepositoryBranch.objects.create(repository=test_repository, branch="releases/*")

    catchall_repo = Repository.objects.create(
        name="catchall-repo",
        repository_group=test_repository.repository_group,
        dvcs_type="git",
        url=url,
        tc_root_url=test_repository.tc_root_url,
    )
    RepositoryBranch.objects.create(repository=catchall_repo, branch="*")

    github_push[0]["payload"]["details"]["event.base.repo.branch"] = "releases/v1"
    PushLoader().process(
        github_push[0]["payload"],
        github_push[0]["exchange"],
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 0


@pytest.mark.django_db
def test_ingest_github_pull_request_routing(github_pr, test_repository, mock_github_pr_commits):
    """PR events route to repos with accepts_pull_requests=True"""
    test_repository.url = github_pr["details"]["event.base.repo.url"].replace(".git", "")
    test_repository.accepts_pull_requests = True
    test_repository.save()
    assert Push.objects.count() == 0
    PushLoader().process(
        github_pr,
        "exchange/taskcluster-github/v1/pull-request",
        "https://firefox-ci-tc.services.mozilla.com",
    )
    assert Push.objects.count() == 1


def test_fetch_push_raises_on_empty_pushes(monkeypatch):
    """Test that a HgPushFetchError is raised when fetch_json returns a dict without 'pushes'"""
    monkeypatch.setattr("treeherder.etl.push_loader.fetch_json", lambda url: {})
    transformer = HgPushTransformer(
        {
            "payload": {
                "repo_url": "https://hg.mozilla.org/try",
                "pushlog_pushes": [{"push_full_json_url": "http://example"}],
            }
        }
    )
    with pytest.raises(HgPushFetchError):
        transformer.fetch_push("http://example", repository="try")
