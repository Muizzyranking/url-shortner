from datetime import datetime, timedelta, timezone


async def test_redirect_to_existing_slug(client):
    await client.post(
        "/api/links", json={"slug": "goto", "target_url": "https://example.com/page"}
    )

    resp = await client.get("/goto", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/page"


async def test_redirect_to_missing_slug_returns_404(client):
    resp = await client.get("/does-not-exist", follow_redirects=False)
    assert resp.status_code == 404


async def test_redirect_to_expired_link_returns_404(client):
    soon = datetime.now(timezone.utc) + timedelta(seconds=1)
    await client.post(
        "/api/links",
        json={
            "slug": "expiring",
            "target_url": "https://example.com",
            "expires_at": soon.isoformat(),
        },
    )
    import asyncio

    await asyncio.sleep(1.2)

    resp = await client.get("/expiring", follow_redirects=False)
    assert resp.status_code == 404


async def test_redirect_increments_click_count(client):
    await client.post(
        "/api/links", json={"slug": "counted", "target_url": "https://example.com"}
    )

    await client.get("/counted", follow_redirects=False)
    await client.get("/counted", follow_redirects=False)

    listing = await client.get("/api/links")
    link = next(item for item in listing.json()["links"] if item["slug"] == "counted")
    assert link["click_count"] == 2
