"""Tests for app/routes.py — all 6 API/HTML endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_connection
from app.routes import router, get_db


@pytest.fixture
def app_with_test_db(test_db_path: str) -> FastAPI:
    """Create a fresh FastAPI app with test DB injected via dependency override."""

    def override_get_db() -> Iterator[Connection]:
        conn = get_connection(test_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def client(app_with_test_db: FastAPI) -> Iterator[TestClient]:
    """Yield a TestClient scoped to the test app."""
    with TestClient(app_with_test_db) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════
# HTML page
# ═══════════════════════════════════════════════════════════════════

class TestIndex:
    def test_returns_html(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_contains_chart_containers(self, client: TestClient):
        resp = client.get("/")
        html = resp.text
        assert "mini-ts-chart" in html
        assert "heatmap-chart" in html
        assert "top-sessions-chart" in html
        assert "model-chart" in html
        assert "project-chart" in html
        assert "agent-chart" in html
        assert "cost-chart" in html
        assert "cache-chart" in html
        assert "overview-cards" in html

    def test_contains_echarts_cdn(self, client: TestClient):
        resp = client.get("/")
        assert "echarts" in resp.text

    def test_contains_db_path(self, client: TestClient):
        resp = client.get("/")
        assert ".db" in resp.text


# ═══════════════════════════════════════════════════════════════════
# /api/overview
# ═══════════════════════════════════════════════════════════════════

class TestApiOverview:
    def test_returns_json(self, client: TestClient):
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_has_all_keys(self, client: TestClient):
        resp = client.get("/api/overview")
        data = resp.json()
        expected = {
            "total_tokens", "total_input_tokens", "total_output_tokens",
            "total_reasoning_tokens", "total_cache_read_tokens",
            "total_cache_write_tokens", "total_cost", "total_sessions",
            "total_messages", "paid_messages",
        }
        assert set(data.keys()) == expected

    def test_counts_match_fixture(self, client: TestClient):
        resp = client.get("/api/overview")
        data = resp.json()
        assert data["total_messages"] == 21
        assert data["total_sessions"] == 10
        assert data["paid_messages"] == 11


# ═══════════════════════════════════════════════════════════════════
# /api/tokens-by-date
# ═══════════════════════════════════════════════════════════════════

class TestApiTokensByDate:
    def test_returns_json_array(self, client: TestClient):
        resp = client.get("/api/tokens-by-date")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_default_granularity_is_day(self, client: TestClient):
        resp = client.get("/api/tokens-by-date")
        data = resp.json()
        # Day format is YYYY-MM-DD (10 chars)
        assert all(len(row["date"]) == 10 for row in data)

    def test_month_granularity(self, client: TestClient):
        resp = client.get("/api/tokens-by-date?granularity=month")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # Month format is YYYY-MM (7 chars)
        assert all(len(row["date"]) == 7 for row in data)

    def test_week_granularity(self, client: TestClient):
        resp = client.get("/api/tokens-by-date?granularity=week")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_row_has_all_keys(self, client: TestClient):
        resp = client.get("/api/tokens-by-date")
        row = resp.json()[0]
        assert "date" in row
        assert "input" in row
        assert "output" in row
        assert "reasoning" in row
        assert "cache_read" in row
        assert "cache_write" in row
        assert "total" in row


# ═══════════════════════════════════════════════════════════════════
# /api/tokens-by-model
# ═══════════════════════════════════════════════════════════════════

class TestApiTokensByModel:
    def test_returns_json_array(self, client: TestClient):
        resp = client.get("/api/tokens-by-model")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_row_has_all_keys(self, client: TestClient):
        resp = client.get("/api/tokens-by-model")
        row = resp.json()[0]
        assert "model" in row
        assert "provider" in row
        assert "input" in row
        assert "output" in row
        assert "reasoning" in row
        assert "cache_read" in row
        assert "cache_write" in row
        assert "cost" in row
        assert "message_count" in row


# ═══════════════════════════════════════════════════════════════════
# /api/tokens-by-project
# ═══════════════════════════════════════════════════════════════════

class TestApiTokensByProject:
    def test_returns_json_array(self, client: TestClient):
        resp = client.get("/api/tokens-by-project")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_row_has_all_keys(self, client: TestClient):
        resp = client.get("/api/tokens-by-project")
        row = resp.json()[0]
        assert "project" in row
        assert "input" in row
        assert "output" in row
        assert "reasoning" in row
        assert "cache_read" in row
        assert "cache_write" in row
        assert "cost" in row
        assert "session_count" in row

    def test_project_names_are_derived(self, client: TestClient):
        resp = client.get("/api/tokens-by-project")
        data = resp.json()
        names = {r["project"] for r in data}
        assert "project-navigator" in names
        assert "volume_balance" in names
        assert "Global" in names


# ═══════════════════════════════════════════════════════════════════
# /api/cost-breakdown
# ═══════════════════════════════════════════════════════════════════

class TestApiCostBreakdown:
    def test_returns_json_array(self, client: TestClient):
        resp = client.get("/api/cost-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_row_has_all_keys(self, client: TestClient):
        resp = client.get("/api/cost-breakdown")
        row = resp.json()[0]
        assert "model" in row
        assert "provider" in row
        assert "cost" in row
        assert "token_count" in row
        assert "message_count" in row

    def test_sorted_by_cost_descending(self, client: TestClient):
        resp = client.get("/api/cost-breakdown")
        data = resp.json()
        for i in range(len(data) - 1):
            assert data[i]["cost"] >= data[i + 1]["cost"]


# ═══════════════════════════════════════════════════════════════════
# Date-filtered API endpoints
# ═══════════════════════════════════════════════════════════════════

class TestApiOverviewWithDateFilter:
    """``start_date`` / ``end_date`` params for /api/overview."""

    def test_date_params_reduce_counts(self, client: TestClient):
        resp = client.get("/api/overview?start_date=2026-03-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_messages"] == 9   # 13 - 4 Feb msgs
        assert data["total_sessions"] == 6   # 8 - 2 Feb sessions

    def test_both_dates(self, client: TestClient):
        resp = client.get("/api/overview?start_date=2026-03-01&end_date=2026-04-30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_messages"] == 6
        assert data["total_sessions"] == 4

    def test_empty_date_params_same_as_no_params(self, client: TestClient):
        resp_empty = client.get("/api/overview?start_date=&end_date=")
        resp_none = client.get("/api/overview")
        assert resp_empty.status_code == 200
        assert resp_none.status_code == 200
        # Empty strings should be treated as None → full dataset
        assert resp_empty.json() == resp_none.json()


class TestApiTokensByDateWithDateFilter:
    """Date filtering for /api/tokens-by-date."""

    def test_date_filter_excludes_data(self, client: TestClient):
        resp = client.get("/api/tokens-by-date?granularity=month&start_date=2026-03-01")
        assert resp.status_code == 200
        data = resp.json()
        dates = {r["date"] for r in data}
        assert "2026-02" not in dates

    def test_date_filter_works_with_granularity(self, client: TestClient):
        resp = client.get(
            "/api/tokens-by-date?granularity=month&start_date=2026-03-01&end_date=2026-04-30"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["date"] in ("2026-03", "2026-04") for r in data)


class TestApiTokensByModelWithDateFilter:
    """Date filtering for /api/tokens-by-model."""

    def test_excludes_feb_only_models(self, client: TestClient):
        resp = client.get("/api/tokens-by-model?start_date=2026-03-01")
        assert resp.status_code == 200
        models = {r["model"] for r in resp.json()}
        assert "deepseek-v4-flash" not in models


class TestApiTokensByProjectWithDateFilter:
    """Date filtering for /api/tokens-by-project."""

    def test_excludes_feb_only_projects(self, client: TestClient):
        resp = client.get("/api/tokens-by-project?start_date=2026-03-01")
        assert resp.status_code == 200
        projects = {r["project"] for r in resp.json()}
        assert "project-navigator" not in projects


class TestApiCostBreakdownWithDateFilter:
    """Date filtering for /api/cost-breakdown."""

    def test_excludes_feb_models(self, client: TestClient):
        resp = client.get("/api/cost-breakdown?start_date=2026-03-01")
        assert resp.status_code == 200
        data = resp.json()
        models = {r["model"] for r in data}
        assert "deepseek-v4-pro" not in models
        assert len(data) > 0
        # Top should now be MiniMax-M2.7
        assert data[0]["model"] == "MiniMax-M2.7"


# ═══════════════════════════════════════════════════════════════════
# /api/data?view=agent-breakdown
# ═══════════════════════════════════════════════════════════════════

class TestApiAgentBreakdown:
    def test_agent_breakdown_view(self, client):
        resp = client.get("/api/data?view=agent-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "agent" in data[0]
            assert "total_tokens" in data[0]

    def test_agent_breakdown_has_all_keys(self, client):
        resp = client.get("/api/data?view=agent-breakdown")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            expected = {"agent", "total_tokens", "input", "output", "reasoning", "cache_read", "cache_write", "message_count"}
            assert expected.issubset(data[0].keys())


# ═══════════════════════════════════════════════════════════════════
# /api/data?view=usage-heatmap
# ═══════════════════════════════════════════════════════════════════

class TestApiUsageHeatmap:
    def test_usage_heatmap_view(self, client):
        resp = client.get("/api/data?view=usage-heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ═══════════════════════════════════════════════════════════════════
# /api/data?view=model-efficiency
# ═══════════════════════════════════════════════════════════════════

class TestApiModelEfficiency:
    def test_model_efficiency_view(self, client):
        resp = client.get("/api/data?view=model-efficiency")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_model_efficiency_keys(self, client):
        resp = client.get("/api/data?view=model-efficiency")
        assert resp.status_code == 200
        data = resp.json()
        if data:
            expected = {"model", "provider", "total_tokens", "total_cost",
                        "cost_per_1k_tokens", "input_output_ratio",
                        "cache_hit_ratio", "message_count"}
            assert expected.issubset(data[0].keys())


# ═══════════════════════════════════════════════════════════════════
# /api/data?view=all
# ═══════════════════════════════════════════════════════════════════

class TestApiAllData:
    def test_all_view_returns_200(self, client):
        resp = client.get("/api/data?view=all")
        assert resp.status_code == 200

    def test_all_view_has_10_keys(self, client):
        resp = client.get("/api/data?view=all")
        data = resp.json()
        expected_keys = {
            "overview", "tokens_by_date", "tokens_by_model",
            "tokens_by_project", "cost_breakdown", "agent_breakdown",
            "model_efficiency", "usage_heatmap", "top_sessions",
            "cache_efficiency",
        }
        assert data.keys() == expected_keys

    def test_all_overview_shape(self, client):
        resp = client.get("/api/data?view=all")
        ov = resp.json()["overview"]
        for key in ("total_tokens", "total_cost", "total_sessions", "total_messages"):
            assert key in ov

    def test_all_date_filter_reflected(self, client):
        full = client.get("/api/data?view=all").json()
        filtered = client.get("/api/data?view=all&start_date=2026-03-01&end_date=2026-04-30").json()
        assert filtered["overview"]["total_messages"] < full["overview"]["total_messages"]
        assert filtered["overview"]["total_sessions"] < full["overview"]["total_sessions"]

    def test_all_granularity_reflected(self, client):
        day = client.get("/api/data?view=all&granularity=day").json()
        month = client.get("/api/data?view=all&granularity=month").json()
        assert len(day["tokens_by_date"]) >= len(month["tokens_by_date"])

    def test_all_limit_reflected(self, client):
        data = client.get("/api/data?view=all&limit=5").json()
        assert len(data["top_sessions"]) <= 5

    def test_individual_views_still_work(self, client):
        """Backward compat: all 10 individual views still return 200."""
        views = [
            "overview", "tokens-by-date", "tokens-by-model", "tokens-by-project",
            "cost-breakdown", "agent-breakdown", "model-efficiency", "usage-heatmap",
            "top-sessions", "cache-efficiency",
        ]
        for v in views:
            resp = client.get(f"/api/data?view={v}")
            assert resp.status_code == 200, f"view={v} returned {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════
# /api/data (unified endpoint — not yet implemented)
# ═══════════════════════════════════════════════════════════════════

class TestUnifiedEndpoint:
    def test_overview_view_returns_200(self, client):
        resp = client.get("/api/data?view=overview")
        assert resp.status_code == 200

    def test_invalid_view_returns_400(self, client):
        resp = client.get("/api/data?view=nonexistent")
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_missing_view_returns_400(self, client):
        resp = client.get("/api/data")
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_invalid_view_lists_valid_views(self, client):
        resp = client.get("/api/data?view=invalid")
        data = resp.json()
        assert "overview" in data.get("error", "")


# ═══════════════════════════════════════════════════════════════════
# Backward-compatibility redirects (not yet implemented)
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    def test_overview_redirects(self, client):
        resp = client.get("/api/overview", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/data?view=overview" in resp.headers.get("location", "")

    def test_tokens_by_date_redirects(self, client):
        resp = client.get("/api/tokens-by-date", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/data?view=tokens-by-date" in resp.headers.get("location", "")

    def test_tokens_by_model_redirects(self, client):
        resp = client.get("/api/tokens-by-model", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/data?view=tokens-by-model" in resp.headers.get("location", "")

    def test_tokens_by_project_redirects(self, client):
        resp = client.get("/api/tokens-by-project", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/data?view=tokens-by-project" in resp.headers.get("location", "")

    def test_cost_breakdown_redirects(self, client):
        resp = client.get("/api/cost-breakdown", follow_redirects=False)
        assert resp.status_code == 307
        assert "/api/data?view=cost-breakdown" in resp.headers.get("location", "")
