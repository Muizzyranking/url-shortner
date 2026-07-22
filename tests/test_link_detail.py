async def test_get_link_detail_returns_aggregates(client):
    await client.post(
        "/api/links", json={"slug": "detailed", "target_url": "https://example.com"}
    )
    await client.get("/detailed", follow_redirects=False)
    await client.get("/detailed", follow_redirects=False)

    resp = await client.get("/api/links/detailed")
    assert resp.status_code == 200
    body = resp.json()

    assert body["click_count"] == 2
    assert body["clicks_last_24h"] == 2
    assert body["clicks_last_7d"] == 2
    assert body["unique_visitors"] == 1
    assert body["last_clicked_at"] is not None
    assert len(body["daily_clicks"]) == 14
    assert body["daily_clicks"][-1]["count"] == 2


async def test_get_link_detail_not_found_returns_404(client):
    resp = await client.get("/api/links/nope")
    assert resp.status_code == 404


async def test_get_link_detail_zero_clicks(client):
    await client.post(
        "/api/links", json={"slug": "unclicked", "target_url": "https://example.com"}
    )

    resp = await client.get("/api/links/unclicked")
    assert resp.status_code == 200
    body = resp.json()
    assert body["click_count"] == 0
    assert body["clicks_last_24h"] == 0
    assert body["unique_visitors"] == 0
    assert body["last_clicked_at"] is None
    assert all(day["count"] == 0 for day in body["daily_clicks"])
