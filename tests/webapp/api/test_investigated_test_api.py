from django.urls import reverse

from treeherder.model.models import JobType, Push


def test_investigated_test_api(client, test_repository, sample_push, test_sheriff):
    push_obj = Push.objects.first()
    if not push_obj:
        from treeherder.etl.push import store_push_data

        store_push_data(test_repository, sample_push)
        push_obj = Push.objects.first()

    rev = push_obj.revision

    resp = client.get(
        reverse("investigated-tests-list", kwargs={"project": test_repository.name})
        + f"?revision={rev}"
    )
    assert resp.status_code == 200

    client.force_authenticate(user=test_sheriff)

    # POST create
    JobType.objects.create(name="test_job_type", symbol="tjt")
    resp = client.post(
        reverse("investigated-tests-list", kwargs={"project": test_repository.name})
        + f"?revision={rev}",
        {"test": "my_test", "job_name": "test_job_type", "job_symbol": "tjt"},
        content_type="application/json",
    )
    assert resp.status_code == 201

    # POST duplicate -> 400
    resp = client.post(
        reverse("investigated-tests-list", kwargs={"project": test_repository.name})
        + f"?revision={rev}",
        {"test": "my_test", "job_name": "test_job_type", "job_symbol": "tjt"},
        content_type="application/json",
    )
    assert resp.status_code == 400

    # DELETE 404
    resp = client.delete(
        reverse("investigated-tests-detail", kwargs={"project": test_repository.name, "pk": 99999})
    )
    assert resp.status_code == 404


def test_classification_delete(client, test_user, test_sheriff):
    url = reverse("classification-list", kwargs={"project": "mozilla-central"})

    # Non-staff -> 403
    client.force_authenticate(user=test_user)
    resp = client.delete(url, [], content_type="application/json")
    assert resp.status_code == 403

    # Staff empty jobs -> 404
    client.force_authenticate(user=test_sheriff)
    resp = client.delete(url, [], content_type="application/json")
    assert resp.status_code == 404

    # Staff valid jobs -> 200
    resp = client.delete(url, [{"id": 1}], content_type="application/json")
    assert resp.status_code == 200
