from django.urls import reverse


def test_infra_compare_missing_params(client):
    resp = client.get(reverse("infra-compare"))
    assert resp.status_code == 400


def test_infra_compare_with_interval(client, test_repository):
    resp = client.get(
        reverse("infra-compare"),
        {"project": test_repository.name, "interval": 86400},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_infra_compare_with_revision(client, test_repository, sample_push):
    push_rev = sample_push[0]["revision"]
    resp = client.get(
        reverse("infra-compare"),
        {"project": test_repository.name, "revision": push_rev},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_infra_compare_with_dates(client, test_repository):
    resp = client.get(
        reverse("infra-compare"),
        {
            "project": test_repository.name,
            "startday": "2024-01-01",
            "endday": "2024-01-02",
        },
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
