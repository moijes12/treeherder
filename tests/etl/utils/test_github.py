from unittest.mock import MagicMock, patch
from treeherder.utils import github

def test_get_releases():
    with patch("treeherder.utils.github.github") as mock_gh:
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        github.get_releases("owner", "repo")
        mock_gh.get_repo.assert_called_with("owner/repo")
        mock_repo.get_releases.assert_called_once()

def test_get_repo():
    with patch("treeherder.utils.github.github") as mock_gh:
        github.get_repo("owner", "repo")
        mock_gh.get_repo.assert_called_with("owner/repo")

def test_get_all_commits():
    with patch("treeherder.utils.github.github") as mock_gh:
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        github.get_all_commits("owner", "repo", params={"since": "date"})
        mock_repo.get_commits.assert_called_with(since="date")

def test_get_commit():
    with patch("treeherder.utils.github.github") as mock_gh:
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        github.get_commit("owner", "repo", "sha")
        mock_repo.get_commit.assert_called_with("sha")

def test_compare_shas():
    with patch("treeherder.utils.github.github") as mock_gh:
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_comparison = MagicMock()
        mock_repo.compare.return_value = mock_comparison
        mock_comparison.commits = [MagicMock(), MagicMock()]
        commits = github.compare_shas("owner", "repo", "base", "head")
        mock_repo.compare.assert_called_with("base", "head")
        assert len(commits) == 2
