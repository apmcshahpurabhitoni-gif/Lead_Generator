"""Canonical discovery -> research -> scoring -> persistence workflow."""

import logging
from typing import Any

from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead

log = logging.getLogger(__name__)


async def process_candidates(
    db: Database,
    job_id: int,
    candidates: list[dict[str, Any]],
    industry: str,
    city: str,
) -> tuple[int, int]:
    saved = 0
    failed = 0
    query = (
        f"businesses in {city}"
        if industry.strip().lower() in {"all", "business", "businesses"}
        else f"{industry} in {city}"
    )

    for candidate in candidates:
        try:
            # Keep the requested search context separate from the verified
            # candidate classification so the dashboard can explain both.
            candidate["requested_industry"] = industry
            candidate["requested_city"] = city

            research = await research_business(candidate)
            research["search"] = {
                **(research.get("search") or {}),
                "query": query,
                "requested_industry": industry,
                "requested_city": city,
            }
            research["google"] = {
                **(research.get("google") or {}),
                "local_rank": candidate.get("google_local_rank"),
                "provider_rank": candidate.get("google_provider_rank"),
                "match_confidence": candidate.get("google_match_confidence"),
                "rating": candidate.get("google_rating"),
                "review_count": candidate.get("google_review_count"),
                "maps_url": candidate.get("google_maps_url"),
                "types": candidate.get("google_types", []),
            }

            score = score_lead(research)
            research["score_breakdown"] = score.get("breakdown", [])

            bid, _ = await db.upsert_business(candidate)
            if not bid:
                failed += 1
                continue

            await db.save_research_and_score(bid, research, score)

            # search_results is the authoritative relationship between a
            # discovery job and the leads returned by that discovery.
            await db.add_search_result(
                job_id,
                bid,
                candidate.get("google_provider_rank")
                or candidate.get("google_local_rank"),
            )
            saved += 1

        except Exception:
            failed += 1
            log.exception(
                "lead processing failed | city=%s industry=%s",
                city,
                industry,
            )

    return saved, failed


async def run_discovery_job(
    job_id: int,
    city: str,
    industry: str,
    limit: int,
) -> None:
    db = Database()
    processed = 0
    saved = 0
    failed = 0

    try:
        safe_limit = max(1, min(int(limit), 50))
        candidates = await discover_businesses(city, industry, safe_limit)
        processed = len(candidates)
        saved, failed = await process_candidates(
            db, job_id, candidates, industry, city
        )
        await db.finish_job(job_id, processed, saved, failed)
    except Exception as exc:
        log.exception(
            "discovery job failed | city=%s industry=%s",
            city,
            industry,
        )
        await db.finish_job(
            job_id,
            processed,
            saved,
            max(failed, 1),
            str(exc)[:1000],
        )
