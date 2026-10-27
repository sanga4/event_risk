"""Public provider discovery adapters, with conservative bounded pagination.

Discovery is independent of publication/redisplay rights, historical completeness
and real-world event reconciliation. NEVER turn contract titles into verified
canonical events without a source-backed mapping review.
"""
from __future__ import annotations
from urllib.parse import urlencode
import json
import time

KALSHI="https://external-api.kalshi.com/trade-api/v2"
POLYMARKET="https://gamma-api.polymarket.com"
MAX_PAGES=100
PAGE_SIZE=100
def contract_record(provider,market,event=None):
    if not isinstance(market,dict):return None
    if provider=="kalshi":
        market_id=str(market.get("ticker") or "")
        event_id=str(market.get("event_ticker") or (event or {}).get("event_ticker") or "")
        title=str(market.get("title") or market.get("subtitle") or "")
        status=str(market.get("status") or "unknown")
        close_at=market.get("close_time") or market.get("expected_expiration_time")
        source_url="https://kalshi.com/markets/"+market_id.lower() if market_id else None
    elif provider=="polymarket":
        market_id=str(market.get("id") or market.get("conditionId") or "")
        event_id=str((event or {}).get("id") or market.get("eventId") or "")
        title=str(market.get("question") or market.get("groupItemTitle") or "")
        status="closed" if market.get("closed") else "active" if market.get("active") else "unknown"
        close_at=market.get("endDate")
        slug=(event or {}).get("slug") or market.get("slug")
        source_url="https://polymarket.com/event/"+str(slug) if slug else None
    else:raise ValueError("Unknown provider")
    if not market_id:return None
    return {"id":"contract:"+provider+":"+market_id,"provider":provider,
            "native_market_id":market_id,"native_event_id":event_id,
            "market_title":title[:400],"status":status,
            "close_at":close_at,"source_url":source_url,
            "canonical_real_world_event_id":None,
            "canonical_event_mapping_status":"UNMAPPED_REQUIRES_REVIEW",
            "price_not_fetched":True,"licensing_review_required":True,
            "provider_published_original_pit_verified":False}
def catalog_pages(provider,fetch,*,statuses=("open",),max_pages=3,page_size=PAGE_SIZE,
                  sleep_seconds=0):
    """fetch(url)->dict/list; cap pagination and keep native metadata unmodified.

    Default is a small explicit batch, not an unbounded history scraper.
    Run broader ingestion only after verifying provider rights and rate limits.
    """
    if provider not in ("kalshi","polymarket"):raise ValueError("Invalid provider")
    if not isinstance(page_size,int) or not 1<=page_size<=200:raise ValueError("page_size")
    if not isinstance(max_pages,int) or not 1<=max_pages<=MAX_PAGES:raise ValueError("max_pages")
    if not statuses:raise ValueError("statuses")
    seen=set()
    emitted=0
    for status in statuses:
        cursor=""
        for page in range(max_pages):
            if provider=="kalshi":
                params={"limit":page_size,"with_nested_markets":"true"}
                if status!="all":params["status"]=status
                if cursor:params["cursor"]=cursor
                url=KALSHI+"/events?"+urlencode(params)
                response=fetch(url)
                if not isinstance(response,dict):raise ValueError("Kalshi response shape")
                events=response.get("events") or []
                next_cursor=response.get("cursor") or ""
            else:
                params={"limit":page_size,"offset":page*page_size}
                if status=="open":params.update({"active":"true","closed":"false"})
                elif status=="closed":params["closed"]="true"
                elif status not in ("all",):raise ValueError("Unsupported Polymarket status")
                url=POLYMARKET+"/events?"+urlencode(params)
                response=fetch(url)
                if not isinstance(response,list):raise ValueError("Polymarket events shape")
                events=response
                next_cursor=None
            for event in events:
                if not isinstance(event,dict):continue
                for market in event.get("markets",[]) or []:
                    record=contract_record(provider,market,event)
                    if record and record["id"] not in seen:
                        seen.add(record["id"]);emitted+=1
                        yield record
            if sleep_seconds:time.sleep(sleep_seconds)
            if provider=="kalshi":
                if not next_cursor or next_cursor==cursor:break
                cursor=next_cursor
            elif len(events)<page_size:break
def coverage_manifest(provider,records,as_of):
    unique={r["id"]:r for r in records if r.get("provider")==provider}
    statuses={}
    for record in unique.values():
        status=record.get("status") or "unknown"
        statuses[status]=statuses.get(status,0)+1
    return {"provider":provider,"captured_at_utc":as_of,"distinct_contracts":len(unique),
            "lifecycle_counts":statuses,"all_provider_contracts_included":False,
            "historical_backfill_completed":False,"rights_approved_for_redisplay":False,
            "source_question_to_canonical_event_links_verified":0}
