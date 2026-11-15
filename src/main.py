"""EU Public Tender Finder: search TED (the official EU tenders journal) and return clean rows."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from apify import Actor

from .ted import API_URL, FIELDS, PAGE_LIMIT, InputError, build_query, shape_notice

CHARGE_EVENT = "tender"
SEEN_STORE = "ted-seen-notices"


async def fetch_page(client: httpx.AsyncClient, query: str, page: int, limit: int) -> dict[str, Any]:
    body = {"query": query, "fields": FIELDS, "page": page, "limit": limit, "paginationMode": "PAGE_NUMBER"}
    last_error = ""
    for attempt in range(4):
        try:
            resp = await client.post(API_URL, json=body)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 400:
                raise InputError(f"TED rejected the search: {resp.text[:500]}")
            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
        await asyncio.sleep(2 ** attempt * 2)
    raise RuntimeError(f"TED search failed after retries: {last_error}")


async def main() -> None:
    async with Actor:
        inp: dict[str, Any] = await Actor.get_input() or {}
        max_results = max(1, min(int(inp.get("maxResults") or 100), 10000))
        languages = [l for l in (inp.get("preferredLanguages") or ["en"]) if l]
        only_new = bool(inp.get("onlyNewSinceLastRun", False))
        monitor_key = (inp.get("monitorName") or "default").strip() or "default"

        try:
            query = build_query(inp)
        except InputError as exc:
            await Actor.fail(status_message=f"Invalid input: {exc}")
            return
        Actor.log.info(f"TED query: {query}")

        seen: set[str] = set()
        history: list[str] = []
        store = None
        if only_new:
            store = await Actor.open_key_value_store(name=SEEN_STORE)
            history = list(await store.get_value(monitor_key) or [])
            seen = set(history)
            Actor.log.info(f"Monitor '{monitor_key}': {len(seen)} notices already delivered earlier")

        pushed = 0
        total = None
        page = 1
        new_ids: list[str] = []
        timeout = httpx.Timeout(60.0)
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "apify-ted-tender-finder"}) as client:
            while pushed < max_results:
                try:
                    data = await fetch_page(client, query, page, PAGE_LIMIT)
                except InputError as exc:
                    await Actor.fail(status_message=str(exc))
                    return
                if total is None:
                    total = data.get("totalNoticeCount")
                    Actor.log.info(f"Matching notices on TED: {total}")
                notices = data.get("notices") or []
                if not notices:
                    break
                batch = []
                batch_ids: set[str] = set()
                for n in notices:
                    item = shape_notice(n, languages)
                    nid = item["noticeId"]
                    if not nid or nid in seen or nid in batch_ids:
                        continue
                    batch_ids.add(nid)
                    batch.append(item)
                    if pushed + len(batch) >= max_results:
                        break
                if batch:
                    result = await Actor.push_data(batch, charged_event_name=CHARGE_EVENT)
                    accepted = len(batch)
                    if result is not None and result.event_charge_limit_reached:
                        accepted = result.charged_count if result.charged_count else accepted
                    pushed += accepted
                    delivered = [i["noticeId"] for i in batch[:accepted]]
                    new_ids.extend(delivered)
                    seen.update(delivered)
                    history.extend(delivered)
                    if result is not None and result.event_charge_limit_reached:
                        Actor.log.info("Reached the maximum charge set for this run. Stopping.")
                        break
                if len(notices) < PAGE_LIMIT or page * PAGE_LIMIT >= 15000:
                    break
                page += 1

        if store is not None:
            await store.set_value(monitor_key, history[-50000:])

        msg = f"Delivered {pushed} tender notices" + (f" (of {total} matching on TED)" if total is not None else "")
        if only_new:
            msg += f"; new since last run: {len(new_ids)}"
        Actor.log.info(msg)
        await Actor.set_status_message(msg, is_terminal=True)
