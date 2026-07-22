from datetime import datetime, timedelta, timezone


async def test_create_link_with_custom_slug(client):
    resp = await client.post(
        "/api/links", json={"slug": "my-slug", "target_url": "https://example.com"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "my-slug"
    assert body["target_url"] == "https://example.com/"
    assert body["click_count"] == 0
    assert body["expires_at"] is None


async def test_create_link_auto_generates_slug(client):
    resp = await client.post("/api/links", json={"target_url": "https://example.com"})
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["slug"]) == 7


async def test_create_link_rejects_duplicate_slug(client):
    payload = {"slug": "dupe", "target_url": "https://example.com"}
    first = await client.post("/api/links", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/links", json=payload)
    assert second.status_code == 409
    assert "already in use" in second.json()["detail"]


async def test_create_link_rejects_invalid_url(client):
    resp = await client.post("/api/links", json={"target_url": "not-a-url"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid request"


async def test_create_link_rejects_invalid_slug_charset(client):
    resp = await client.post(
        "/api/links", json={"slug": "bad slug!", "target_url": "https://example.com"}
    )
    assert resp.status_code == 400


async def test_create_link_expire_after(client):
    resp = await client.post(
        "/api/links",
        json={"target_url": "https://example.com", "expire_after": 60},
    )
    assert resp.status_code == 201
    body = resp.json()
    expires_at = datetime.fromisoformat(body["expires_at"])
    now = datetime.now(timezone.utc)
    assert now < expires_at < now + timedelta(seconds=65)


async def test_create_link_earliest_expiry_wins(client):
    soon = datetime.now(timezone.utc) + timedelta(seconds=30)
    resp = await client.post(
        "/api/links",
        json={
            "target_url": "https://example.com",
            "expires_at": soon.isoformat(),
            "expire_after": 3600,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert expires_at < datetime.now(timezone.utc) + timedelta(seconds=35)


async def test_list_links_returns_created_links(client):
    await client.post("/api/links", json={"slug": "one", "target_url": "https://a.com"})
    await client.post("/api/links", json={"slug": "two", "target_url": "https://b.com"})

    resp = await client.get("/api/links")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    slugs = {link["slug"] for link in body["links"]}
    assert slugs == {"one", "two"}
    assert "created_at" in body["links"][0]


async def test_delete_link_removes_it(client):
    await client.post(
        "/api/links", json={"slug": "gone", "target_url": "https://a.com"}
    )

    resp = await client.delete("/api/links/gone")
    assert resp.status_code == 204

    listing = await client.get("/api/links")
    assert listing.json()["count"] == 0


async def test_delete_nonexistent_link_returns_404(client):
    resp = await client.delete("/api/links/nope")
    assert resp.status_code == 404
