from fastapi.testclient import TestClient


def test_health_endpoint_returns_200(client: TestClient) -> None:
    """ヘルスチェックエンドポイントが200を返すことを確認する"""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_has_required_fields(client: TestClient) -> None:
    """ヘルスチェックレスポンスに必要なフィールドが含まれることを確認する"""
    response = client.get("/health")
    body = response.json()

    assert "status" in body
    assert "version" in body
    assert "services" in body
    assert "database" in body["services"]
    assert "redis" in body["services"]
