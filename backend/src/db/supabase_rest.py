"""
Supabase REST client — HTTP-based wrapper compatible with all Python versions.
Supports insert, upsert, update, select_one, select_many, and delete.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv("backend/.env")


class SupabaseREST:
    def __init__(self) -> None:
        self.base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.base_url or not self.service_key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in backend/.env")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _url(self, table: str) -> str:
        return f"{self.base_url}/rest/v1/{table}"

    # ── Write ────────────────────────────────────────────────────────────────

    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(self._url(table), headers=self.headers, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data[0] if isinstance(data, list) and data else (data or {})

    def upsert(self, table: str, payload: dict[str, Any], on_conflict: str = "id") -> dict[str, Any]:
        """Insert or update if conflict on the specified column."""
        headers = {**self.headers, "Prefer": f"return=representation,resolution=merge-duplicates"}
        resp = httpx.post(self._url(table), headers=headers, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data[0] if isinstance(data, list) and data else (data or {})

    def update(
        self,
        table: str,
        record_id: str,
        payload: dict[str, Any],
        id_col: str = "id",
    ) -> dict[str, Any]:
        params = {id_col: f"eq.{record_id}"}
        resp = httpx.patch(
            self._url(table), headers=self.headers, params=params, json=payload, timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()
        return data[0] if isinstance(data, list) and data else (data or {})

    def delete(self, table: str, record_id: str, id_col: str = "id") -> None:
        params = {id_col: f"eq.{record_id}"}
        resp = httpx.delete(self._url(table), headers=self.headers, params=params, timeout=30.0)
        resp.raise_for_status()

    # ── Read ─────────────────────────────────────────────────────────────────

    def select_one(
        self,
        table: str,
        filters: dict[str, str],
        select: str = "*",
    ) -> dict[str, Any] | None:
        params: dict[str, str] = {"select": select, "limit": "1"}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        resp = httpx.get(self._url(table), headers=self.headers, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data[0] if isinstance(data, list) and data else None

    def select_many(
        self,
        table: str,
        filters: dict[str, str] | None = None,
        select: str = "*",
        order: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select}
        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"
        if order:
            params["order"] = order
        if limit:
            params["limit"] = str(limit)
        if offset:
            params["offset"] = str(offset)

        resp = httpx.get(self._url(table), headers=self.headers, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def select_raw(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        """Raw select with arbitrary PostgREST filter params."""
        resp = httpx.get(self._url(table), headers=self.headers, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
