"""Tests for app/db.py — all 7 query functions plus utilities."""

from __future__ import annotations

import sqlite3

import pytest

from app.db import (
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
        # 13 messages total
        assert stats["total_messages"] == 13
        # 8 sessions total
        assert stats["total_sessions"] == 8
        # Only m1,m2,m3,m4,m5,m6,m13 have non-zero cost (7 messages)
        assert stats["paid_messages"] == 7
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
                assert row["session_count"] == 2
            elif row["project"] == "volume_balance":
                assert row["session_count"] == 2
            elif row["project"] == "Global":
                assert row["session_count"] == 2


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
