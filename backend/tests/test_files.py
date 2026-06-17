from tests.test_strategies import auth_headers, register_and_token


def upload_file(
    client,
    token: str,
    name: str = "strategy-note.json",
    content: bytes = b'{"ok":true}',
):
    return client.post(
        "/api/files/upload",
        headers=auth_headers(token),
        data={"businessType": "strategy", "visibility": "private"},
        files={"file": (name, content, "application/json")},
    )


def test_file_upload_list_download_and_delete_flow(client):
    token = register_and_token(client, "file-alice", "file-alice@example.com")

    upload_response = upload_file(client, token)

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["id"]
    assert uploaded["ownerId"]
    assert uploaded["originalName"] == "strategy-note.json"
    assert uploaded["contentType"] == "application/json"
    assert uploaded["businessType"] == "strategy"
    assert uploaded["visibility"] == "private"
    assert uploaded["downloadUrl"] == f"/api/files/{uploaded['id']}/download"

    list_response = client.get(
        "/api/files?keyword=note&page=1&pageSize=10",
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == uploaded["id"]

    download_response = client.get(
        f"/api/files/{uploaded['id']}/download",
        headers=auth_headers(token),
    )
    assert download_response.status_code == 200
    assert download_response.content == b'{"ok":true}'
    assert "strategy-note.json" in download_response.headers["content-disposition"]

    delete_response = client.delete(
        f"/api/files/{uploaded['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/files/{uploaded['id']}/download",
        headers=auth_headers(token),
    )
    assert missing_response.status_code == 404


def test_file_endpoints_require_login(client):
    response = client.get("/api/files")
    assert response.status_code == 401

    upload_response = client.post(
        "/api/files/upload",
        files={"file": ("note.json", b"{}", "application/json")},
    )
    assert upload_response.status_code == 401


def test_file_upload_rejects_unsupported_type(client):
    token = register_and_token(client, "file-type", "file-type@example.com")

    response = client.post(
        "/api/files/upload",
        headers=auth_headers(token),
        files={"file": ("payload.bin", b"abc", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "暂不支持这种文件类型"


def test_files_are_private_to_owner(client):
    alice_token = register_and_token(client, "file-owner", "file-owner@example.com")
    bob_token = register_and_token(client, "file-intruder", "file-intruder@example.com")

    uploaded = upload_file(client, alice_token, name="owner-note.json").json()

    alice_list = client.get("/api/files", headers=auth_headers(alice_token))
    bob_list = client.get("/api/files", headers=auth_headers(bob_token))

    assert alice_list.status_code == 200
    assert bob_list.status_code == 200
    assert alice_list.json()["total"] == 1
    assert bob_list.json()["total"] == 0

    bob_download = client.get(
        f"/api/files/{uploaded['id']}/download",
        headers=auth_headers(bob_token),
    )
    bob_delete = client.delete(
        f"/api/files/{uploaded['id']}",
        headers=auth_headers(bob_token),
    )

    assert bob_download.status_code == 404
    assert bob_delete.status_code == 404

    cleanup = client.delete(f"/api/files/{uploaded['id']}", headers=auth_headers(alice_token))
    assert cleanup.status_code == 204
