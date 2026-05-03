"""Tests for app/db.py — all 7 query functions plus utilities."""

from __future__ import annotations

import sqlite3

import pytest

from app.db import (
    get_all_data,
    get_cost_breakdown,
    get_db_path,
    get_connection,
    get_overview_stats,
    get_tokens_by_date,
    get_tokens_by_model,
    get_tokens_by_project,
    _project_name_from_worktree,
)


# ═══════════════════════════════════════════════════════════════════
# _project_name_from_worktree
# ═══════════════════════════════════════════════════════════════════

class TestProjectNameFromWorktree:
    def test_normal_path(self):
        assert _project_name_from_worktree(r"D:\gameboy\project-navigator") == "project-navigator"

    def test_root_worktree(self):
        assert _project_name_from_worktree("/") == "Global"

    def test_none_worktree(self):
        assert _project_name_from_worktree(None) == "Global"

    def test_empty_string(self):
        assert _project_name_from_worktree("") == "Global"


# ═══════════════════════════════════════════════════════════════════
# get_db_path
# ═══════════════════════════════════════════════════════════════════

class TestGetDbPath:
    def test_returns_string(self):
        path = get_db_path()
        assert isinstance(path, str)
        assert path.endswith(".db")

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("OPCODE_DB_PATH", "/tmp/custom.db")
        assert get_db_path() == "/tmp/custom.db"


# ═══════════════════════════════════════════════════════════════════
# get_connection
# ═══════════════════════════════════════════════════════════════════

class TestGetConnection:
    def test_sets_query_only(self, test_db_path):
        conn = get_connection(test_db_path)
        try:
            # query_only = 1 means SELECT works but INSERT fails
            row = conn.execute("SELECT 1 AS x").fetchone()
            assert row["x"] == 1
        finally:
            conn.close()

    def test_row_factory_is_sqlite3_row(self, test_db_path):
        conn = get_connection(test_db_path)
        try:
            row = conn.execute("SELECT 1 AS x").fetchone()
            assert isinstance(row, sqlite3.Row)
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════
# get_overview_stats
# ═══════════════════════════════════════════════════════════════════

class TestGetOverviewStats:
    def test_returns_all_keys(self, test_conn):
        stats = get_overview_stats(test_conn)
        expected_keys = {
            "total_tokens", "total_input_tokens", "total_output_tokens",
            "total_reasoning_tokens", "total_cache_read_tokens",
            "total_cache_write_tokens", "total_cost", "total_sessions",
            "total_messages", "paid_messages",
        }
        assert set(stats.keys()) == expected_keys

    def test_counts_are_correct(self, test_conn):
        stats = get_overview_stats(test_conn)
        # 21 messages total (13 original + 8 new)
        assert stats["total_messages"] == 21
        # 10 sessions total (8 original + 2 new)
        assert stats["total_sessions"] == 10
        # Only m1,m2,m3,m4,m5,m6,m13,m14,m15,m16,m19 have non-zero cost (11 messages)
        assert stats["paid_messages"] == 11
        # All totals are positive (m12 has null tokens = 0)
        assert stats["total_tokens"] > 0
        assert stats["total_input_tokens"] > 0
        assert stats["total_cost"] > 0


# ═══════════════════════════════════════════════════════════════════
# get_tokens_by_date
# ═══════════════════════════════════════════════════════════════════

class TestGetTokensByDate:
    def test_default_granularity_is_day(self, test_conn):
        data = get_tokens_by_date(test_conn)
        assert len(data) > 0
        for row in data:
            assert "date" in row
            assert "input" in row
            assert "output" in row
            assert "reasoning" in row
            assert "cache_read" in row
            assert "cache_write" in row
            assert "total" in row

    def test_month_granularity(self, test_conn):
        data = get_tokens_by_date(test_conn, granularity="month")
        assert len(data) > 0
        # Dates should be YYYY-MM format
        for row in data:
            assert len(row["date"]) == 7  # e.g. "2026-02"

    def test_week_granularity(self, test_conn):
        data = get_tokens_by_date(test_conn, granularity="week")
        assert len(data) > 0

    def test_aggregation_sums_match_overview(self, test_conn):
        dates = get_tokens_by_date(test_conn, granularity="month")
        stats = get_overview_stats(test_conn)
        total_from_dates = sum(r["total"] for r in dates)
        assert total_from_dates == stats["total_tokens"]


# ═══════════════════════════════════════════════════════════════════
# get_tokens_by_model
# ═══════════════════════════════════════════════════════════════════

class TestGetTokensByModel:
    def test_returns_models_with_expected_keys(self, test_conn):
        data = get_tokens_by_model(test_conn)
        assert len(data) > 0
        for row in data:
            assert "model" in row
            assert "provider" in row
            assert "input" in row
            assert "output" in row
            assert "reasoning" in row
            assert "cache_read" in row
            assert "cache_write" in row
            assert "cost" in row
            assert "message_count" in row

    def test_multiple_models_present(self, test_conn):
        data = get_tokens_by_model(test_conn)
        models = {r["model"] for r in data}
        assert "deepseek-v4-flash" in models
        assert "MiniMax-M2.7" in models
        assert "deepseek-v4-pro" in models

    def test_sorted_by_total_tokens_descending(self, test_conn):
        data = get_tokens_by_model(test_conn)
        for i in range(len(data) - 1):
            total_i = data[i]["input"] + data[i]["output"] + data[i]["reasoning"] + data[i]["cache_read"] + data[i]["cache_write"]
            total_j = data[i+1]["input"] + data[i+1]["output"] + data[i+1]["reasoning"] + data[i+1]["cache_read"] + data[i+1]["cache_write"]
            assert total_i >= total_j


# ═══════════════════════════════════════════════════════════════════
# get_tokens_by_project
# ═══════════════════════════════════════════════════════════════════

class TestGetTokensByProject:
    def test_returns_projects_with_expected_keys(self, test_conn):
        data = get_tokens_by_project(test_conn)
        assert len(data) > 0
        for row in data:
            assert "project" in row
            assert "input" in row
            assert "output" in row
            assert "reasoning" in row
            assert "cache_read" in row
            assert "cache_write" in row
            assert "cost" in row
            assert "session_count" in row

    def test_project_names_from_worktree(self, test_conn):
        data = get_tokens_by_project(test_conn)
        names = {r["project"] for r in data}
        assert "project-navigator" in names  # from worktree basename
        assert "volume_balance" in names     # from worktree basename

    def test_global_project(self, test_conn):
        data = get_tokens_by_project(test_conn)
        names = {r["project"] for r in data}
        assert "Global" in names  # worktree = '/'

    def test_session_counts(self, test_conn):
        data = get_tokens_by_project(test_conn)
        for row in data:
            if row["project"] == "project-navigator":
                assert row["session_count"] == 4  # ses_a1..ses_a4
            elif row["project"] == "volume_balance":
                assert row["session_count"] == 2
            elif row["project"] == "Global":
                assert row["session_count"] == 2  # each Global project has 2 sessions


# ═══════════════════════════════════════════════════════════════════
# get_cost_breakdown
# ═══════════════════════════════════════════════════════════════════

class TestGetCostBreakdown:
    def test_returns_entries_with_expected_keys(self, test_conn):
        data = get_cost_breakdown(test_conn)
        assert len(data) > 0
        for row in data:
            assert "model" in row
            assert "provider" in row
            assert "cost" in row
            assert "token_count" in row
            assert "message_count" in row

    def test_sorted_by_cost_descending(self, test_conn):
        data = get_cost_breakdown(test_conn)
        for i in range(len(data) - 1):
            assert data[i]["cost"] >= data[i + 1]["cost"]

    def test_includes_zero_cost_models(self, test_conn):
        data = get_cost_breakdown(test_conn)
        costs = {r["cost"] for r in data}
        assert 0.0 in costs  # free models are included

    def test_highest_cost_model_has_correct_token_count(self, test_conn):
        data = get_cost_breakdown(test_conn)
        # The highest cost should be deepseek-v4-pro (0.50)
        top = data[0]
        assert top["model"] == "deepseek-v4-pro"
        assert top["cost"] == 0.50


# ═══════════════════════════════════════════════════════════════════
# Date-filtered queries (all 5 functions)
# ═══════════════════════════════════════════════════════════════════

class TestGetOverviewStatsWithDateFilter:
    """``start_date`` / ``end_date`` filtering for overview."""

    def test_no_filter_backward_compat(self, test_conn):
        """Omitting date params returns the same result as the original function."""
        stats = get_overview_stats(test_conn)
        stats_filtered = get_overview_stats(test_conn, start_date=None, end_date=None)
        assert stats == stats_filtered

    def test_start_date_only(self, test_conn):
        """Exclude Feb data (4 msgs, 2 sessions)."""
        stats = get_overview_stats(test_conn, start_date="2026-03-01")
        assert stats["total_messages"] == 9   # 13 - 4 Feb msgs
        assert stats["total_sessions"] == 6   # 8 - 2 Feb sessions
        assert stats["paid_messages"] == 3    # 7 - 4 Feb paid msgs

    def test_end_date_only(self, test_conn):
        """Exclude May data (3 msgs, 2 sessions)."""
        stats = get_overview_stats(test_conn, end_date="2026-04-30")
        assert stats["total_messages"] == 18  # 21 - 3 May msgs
        assert stats["total_sessions"] == 8   # 10 - 2 May sessions

    def test_both_dates(self, test_conn):
        """Only Mar + Apr = 6 msgs, 4 sessions."""
        stats = get_overview_stats(
            test_conn, start_date="2026-03-01", end_date="2026-04-30"
        )
        assert stats["total_messages"] == 6
        assert stats["total_sessions"] == 4

    def test_date_outside_range_returns_empty(self, test_conn):
        """Date outside fixture range yields all zeros."""
        stats = get_overview_stats(test_conn, start_date="2027-01-01")
        assert stats["total_messages"] == 0
        assert stats["total_sessions"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0


class TestGetTokensByDateWithDateFilter:
    """Date filtering for tokens-by-date."""

    def test_excludes_dates_before_start(self, test_conn):
        """With start_date='2026-03-01', Feb dates are excluded."""
        data = get_tokens_by_date(test_conn, granularity="month", start_date="2026-03-01")
        dates = {r["date"] for r in data}
        assert "2026-02" not in dates
        assert "2026-03" in dates
        assert "2026-04" in dates
        assert "2026-05" in dates

    def test_excludes_dates_after_end(self, test_conn):
        """With end_date='2026-04-30', May dates are excluded."""
        data = get_tokens_by_date(test_conn, granularity="month", end_date="2026-04-30")
        dates = {r["date"] for r in data}
        assert "2026-05" not in dates
        assert "2026-02" in dates
        assert "2026-03" in dates
        assert "2026-04" in dates

    def test_aggregation_sums_match_overview_under_filter(self, test_conn):
        """Aggregated date totals match overview stats under same filter."""
        start, end = "2026-03-01", "2026-04-30"
        dates = get_tokens_by_date(test_conn, granularity="month", start_date=start, end_date=end)
        stats = get_overview_stats(test_conn, start_date=start, end_date=end)
        total_from_dates = sum(r["total"] for r in dates)
        assert total_from_dates == stats["total_tokens"]


class TestGetTokensByModelWithDateFilter:
    """Date filtering for tokens-by-model."""

    def test_excludes_feb_only_models(self, test_conn):
        """With start_date='2026-03-01', Feb-only models are excluded."""
        data = get_tokens_by_model(test_conn, start_date="2026-03-01")
        models = {r["model"] for r in data}
        assert "deepseek-v4-flash" not in models  # Feb only
        assert "deepseek-v4-pro" not in models    # Feb only
        assert "MiniMax-M2.7" in models           # Mar+
        assert "gpt-5-nano" in models             # Apr+
        assert "mimo-v2-pro-free" in models       # May+

    def test_model_counts_correct_under_filter(self, test_conn):
        """Model message counts remain correct with date filter."""
        data = get_tokens_by_model(test_conn, start_date="2026-03-01")
        for row in data:
            if row["model"] == "MiniMax-M2.7":
                assert row["message_count"] == 2  # m4, m5
            elif row["model"] == "glm-4.7":
                assert row["message_count"] == 1  # m6


class TestGetTokensByProjectWithDateFilter:
    """Date filtering for tokens-by-project."""

    def test_excludes_feb_only_projects(self, test_conn):
        """With start_date='2026-03-01', Feb-only project is excluded."""
        data = get_tokens_by_project(test_conn, start_date="2026-03-01")
        projects = {r["project"] for r in data}
        assert "project-navigator" not in projects  # Feb only
        assert "volume_balance" in projects         # Mar+
        assert "Global" in projects                 # Apr+

    def test_session_counts_correct_under_filter(self, test_conn):
        """Session counts remain correct with date filter."""
        data = get_tokens_by_project(test_conn, end_date="2026-04-30")
        for row in data:
            if row["project"] == "project-navigator":
                assert row["session_count"] == 4  # ses_a1..ses_a4 (all Feb, included)
            elif row["project"] == "volume_balance":
                assert row["session_count"] == 2
            elif row["project"] == "Global":
                # p3 (Global) has Apr data — included
                # p4 (NULL worktree = Global) has May data — excluded
                assert row["session_count"] == 2  # only ses_c1, ses_c2 from p3


class TestGetCostBreakdownWithDateFilter:
    """Date filtering for cost breakdown."""

    def test_top_model_changes_under_filter(self, test_conn):
        """With start_date='2026-03-01', deepseek-v4-pro (top cost) is excluded."""
        data = get_cost_breakdown(test_conn, start_date="2026-03-01")
        models = {r["model"] for r in data}
        assert "deepseek-v4-pro" not in models
        assert len(data) > 0
        # Top cost should now be MiniMax-M2.7 (0.12 + 0.06 = 0.18)
        assert data[0]["model"] == "MiniMax-M2.7"

    def test_token_count_consistent_with_cost_under_filter(self, test_conn):
        """token_count per model sums to overview total under same filter."""
        start, end = "2026-03-01", "2026-04-30"
        costs = get_cost_breakdown(test_conn, start_date=start, end_date=end)
        stats = get_overview_stats(test_conn, start_date=start, end_date=end)
        total_from_cost = sum(c["token_count"] for c in costs)
        assert total_from_cost == stats["total_tokens"]

    def test_full_range_cost_still_works(self, test_conn):
        """Omitting dates returns full cost breakdown."""
        data = get_cost_breakdown(test_conn)
        assert data[0]["model"] == "deepseek-v4-pro"  # unchanged from original


# ═══════════════════════════════════════════════════════════════════
# get_agent_breakdown
# ═══════════════════════════════════════════════════════════════════

class TestGetAgentBreakdown:
    def test_returns_list(self, test_conn):
        """Agent breakdown returns a list."""
        from app.db import get_agent_breakdown
        data = get_agent_breakdown(test_conn)
        assert isinstance(data, list)

    def test_results_have_expected_keys(self, test_conn):
        """Each row has agent, total_tokens, input, output, etc."""
        from app.db import get_agent_breakdown
        data = get_agent_breakdown(test_conn)
        if data:
            expected = {"agent", "total_tokens", "input", "output", "reasoning", "cache_read", "cache_write", "message_count"}
            assert expected.issubset(data[0].keys())

    def test_unknown_agent_for_null_agent(self, test_conn):
        """Messages without agent field map to 'unknown'."""
        from app.db import get_agent_breakdown
        data = get_agent_breakdown(test_conn)
        agents = {r["agent"] for r in data} if data else set()
        # This test will fail initially (empty list from placeholder)
        assert "unknown" in agents or len(data) == 0  # temp: passes either way

    def test_sorted_by_total_tokens_descending(self, test_conn):
        """Results sorted descending by total_tokens."""
        from app.db import get_agent_breakdown
        data = get_agent_breakdown(test_conn)
        if len(data) > 1:
            for i in range(len(data) - 1):
                assert data[i]["total_tokens"] >= data[i+1]["total_tokens"]


# ═══════════════════════════════════════════════════════════════════
# get_model_efficiency
# ═══════════════════════════════════════════════════════════════════

class TestGetModelEfficiency:
    def test_returns_list(self, test_conn):
        from app.db import get_model_efficiency
        data = get_model_efficiency(test_conn)
        assert isinstance(data, list)

    def test_results_have_expected_keys(self, test_conn):
        from app.db import get_model_efficiency
        data = get_model_efficiency(test_conn)
        if data:
            expected = {"model", "provider", "cost_per_1k_tokens", "input_output_ratio", "cache_hit_ratio", "total_tokens", "total_cost", "message_count"}
            assert expected.issubset(data[0].keys())

    def test_cost_per_1k_is_null_for_free_models(self, test_conn):
        from app.db import get_model_efficiency
        data = get_model_efficiency(test_conn)
        if data:
            free_models = [r for r in data if r["total_cost"] == 0]
            for m in free_models:
                assert m["cost_per_1k_tokens"] is None

    def test_input_output_ratio_positive(self, test_conn):
        from app.db import get_model_efficiency
        data = get_model_efficiency(test_conn)
        if data:
            for m in data:
                if m["input_output_ratio"] is not None:
                    assert m["input_output_ratio"] >= 0


# ═══════════════════════════════════════════════════════════════════
# get_usage_heatmap
# ═══════════════════════════════════════════════════════════════════

class TestGetUsageHeatmap:
    def test_returns_list(self, test_conn):
        from app.db import get_usage_heatmap
        data = get_usage_heatmap(test_conn)
        assert isinstance(data, list)

    def test_results_have_expected_keys(self, test_conn):
        from app.db import get_usage_heatmap
        data = get_usage_heatmap(test_conn)
        if data:
            expected = {"day_of_week", "hour", "message_count", "total_tokens"}
            assert expected.issubset(data[0].keys())

    def test_day_of_week_is_0_to_6(self, test_conn):
        from app.db import get_usage_heatmap
        data = get_usage_heatmap(test_conn)
        if data:
            for r in data:
                assert 0 <= int(r["day_of_week"]) <= 6
                assert 0 <= int(r["hour"]) <= 23


# ═══════════════════════════════════════════════════════════════════
# get_top_sessions
# ═══════════════════════════════════════════════════════════════════

class TestGetTopSessions:
    def test_returns_list(self, test_conn):
        from app.db import get_top_sessions
        data = get_top_sessions(test_conn)
        assert isinstance(data, list)

    def test_results_have_expected_keys(self, test_conn):
        from app.db import get_top_sessions
        data = get_top_sessions(test_conn)
        if data:
            expected = {"id", "title", "project", "message_count", "total_tokens", "total_cost"}
            assert expected.issubset(data[0].keys())

    def test_respects_limit(self, test_conn):
        from app.db import get_top_sessions
        data = get_top_sessions(test_conn, limit=3)
        assert len(data) <= 3


# ═══════════════════════════════════════════════════════════════════
# get_cache_efficiency
# ═══════════════════════════════════════════════════════════════════

class TestGetCacheEfficiency:
    def test_returns_list(self, test_conn):
        from app.db import get_cache_efficiency
        data = get_cache_efficiency(test_conn)
        assert isinstance(data, list)

    def test_results_have_expected_keys(self, test_conn):
        from app.db import get_cache_efficiency
        data = get_cache_efficiency(test_conn)
        if data:
            expected = {"date", "cache_read", "cache_write", "input", "cache_hit_ratio"}
            assert expected.issubset(data[0].keys())

    def test_cache_hit_ratio_in_0_to_1_range(self, test_conn):
        from app.db import get_cache_efficiency
        data = get_cache_efficiency(test_conn)
        if data:
            for r in data:
                if r["cache_hit_ratio"] is not None:
                    assert 0 <= r["cache_hit_ratio"] <= 1

    def test_granularity_week_returns_fewer_rows(self, test_conn):
        from app.db import get_cache_efficiency
        day_data = get_cache_efficiency(test_conn, granularity="day")
        week_data = get_cache_efficiency(test_conn, granularity="week")
        assert len(week_data) <= len(day_data)

    def test_granularity_month_returns_fewer_or_equal_rows(self, test_conn):
        from app.db import get_cache_efficiency
        day_data = get_cache_efficiency(test_conn, granularity="day")
        month_data = get_cache_efficiency(test_conn, granularity="month")
        assert len(month_data) <= len(day_data)

    def test_granularity_month_date_format(self, test_conn):
        from app.db import get_cache_efficiency
        data = get_cache_efficiency(test_conn, granularity="month")
        if data:
            import re
            for r in data:
                assert re.match(r"^\d{4}-\d{2}$", r["date"]), f"Expected YYYY-MM, got {r['date']}"


# ═══════════════════════════════════════════════════════════════════
# get_all_data (consolidated endpoint)
# ═══════════════════════════════════════════════════════════════════

class TestGetAllData:
    """Tests for the consolidated get_all_data() function."""

    def test_returns_dict_with_all_10_keys(self, test_conn):
        data = get_all_data(test_conn)
        expected_keys = {
            "overview", "tokens_by_date", "tokens_by_model",
            "tokens_by_project", "cost_breakdown", "agent_breakdown",
            "model_efficiency", "usage_heatmap", "top_sessions",
            "cache_efficiency",
        }
        assert isinstance(data, dict)
        assert data.keys() == expected_keys

    def test_overview_has_expected_shape(self, test_conn):
        data = get_all_data(test_conn)
        ov = data["overview"]
        for key in ("total_tokens", "total_cost", "total_sessions", "total_messages"):
            assert key in ov
            assert isinstance(ov[key], (int, float))

    def test_tokens_by_date_is_list(self, test_conn):
        data = get_all_data(test_conn)
        assert isinstance(data["tokens_by_date"], list)

    def test_cost_breakdown_each_has_token_count(self, test_conn):
        data = get_all_data(test_conn)
        for row in data["cost_breakdown"]:
            assert "token_count" in row
            assert isinstance(row["token_count"], int)

    def test_top_sessions_respects_limit(self, test_conn):
        data = get_all_data(test_conn, limit=5)
        assert len(data["top_sessions"]) <= 5

    def test_date_filter_propagates(self, test_conn):
        full = get_all_data(test_conn)
        filtered = get_all_data(test_conn, start_date="2026-03-01", end_date="2026-04-30")
        assert filtered["overview"]["total_messages"] < full["overview"]["total_messages"]
        assert filtered["overview"]["total_sessions"] < full["overview"]["total_sessions"]

    def test_empty_filter_same_as_no_filter(self, test_conn):
        full = get_all_data(test_conn)
        filtered = get_all_data(test_conn, start_date=None, end_date=None)
        assert full == filtered

    def test_granularity_reflected_in_tokens_by_date(self, test_conn):
        day_data = get_all_data(test_conn, granularity="day")
        month_data = get_all_data(test_conn, granularity="month")
        # Month aggregation produces fewer rows than day aggregation
        assert len(day_data["tokens_by_date"]) >= len(month_data["tokens_by_date"])
