from django.urls import reverse


def test_machine_platforms_list(client, transactional_db):
    resp = client.get(reverse("machineplatforms-list"))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
