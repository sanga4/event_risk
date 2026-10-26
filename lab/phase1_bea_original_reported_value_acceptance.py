#!/usr/bin/env python3
"""SELECT-only independent original HTML BEA values and source-clock acceptance.

Never calls the original BEA value producer. Recomputes the 7 PCE and 3 trade
values directly from immutable original publisher HTML, and preserves *false*
provider first-known, consensus, contractual use and institutional beta claims.
"""
import argparse
from datetime import datetime
import hashlib,json,math,re
import bs4
import duckdb

P="eventrisk_factor_lab.main."
SOURCE_URL={
 "aug2026_personal_income":
 "https://www.bea.gov/news/2026/personal-income-and-outlays-August-2026",
 "aug2026_international_trade":
 "https://www.bea.gov/news/2026/us-international-trade-goods-and-services-august-2026"}
TITLES={
 "aug2026_personal_income":"Personal Income and Outlays, August 2026",
 "aug2026_international_trade":"U.S. International Trade in Goods and Services, August 2026"}
PCE=(
 "Current-dollar personal income","Current-dollar DPI","Real DPI",
 "Current-dollar PCE","Real PCE","PCE price index",
 "PCE price index excluding food and energy")
TRADE=("Deficit:","Exports:","Imports:")

def compute_independent(raw,kind):
    soup=bs4.BeautifulSoup(raw,"html.parser")
    names=[x.get_text(" ",strip=True) for x in soup.find_all("h1")]
    if TITLES[kind] not in names:
        raise ValueError("Wrong original BEA publisher headline")
    output={}
    if kind=="aug2026_personal_income":
        tables=soup.select("table.table-md")
        if len(tables)!=1:
            raise ValueError("Original monthly PCE table not found")
        for tr in tables[0].find_all("tr"):
            td=tr.find_all("td",recursive=False)
            if len(td)!=3:continue
            title=td[0].get_text(" ",strip=True)
            if title in PCE:
                if title in output:raise ValueError("Duplicate PCE metric in original source")
                try:
                    prev=float(td[1].get_text(" ",strip=True))
                    observed=float(td[2].get_text(" ",strip=True))
                except ValueError as e:raise ValueError("Invalid original PCE numerical source") from e
                output[title]=("percent_change_from_previous_month",observed,prev)
        if set(output)!=set(PCE):
            raise ValueError("Original seven PCE source fields incomplete")
        return output
    tables=soup.select("table.table-release-trade")
    if len(tables)!=1:raise ValueError("Original trade summary table missing")
    for tr in tables[0].find_all("tr"):
        td=tr.find_all("td",recursive=False)
        if len(td)<2:continue
        title=td[0].get_text(" ",strip=True)
        if title not in TRADE:continue
        label=title.removesuffix(":").lower()+"_reported_magnitude"
        if label in output:raise ValueError("Duplicate original trade amount")
        m=re.fullmatch(r"\$([\d,]+\.\d+) Billion",td[1].get_text(" ",strip=True))
        if not m:raise ValueError("Trade dollar native unit or value changed")
        output[label]=("usd_billions",float(m.group(1).replace(",","")),None)
    if set(output)!={x.removesuffix(":").lower()+"_reported_magnitude" for x in TRADE}:
        raise ValueError("Original three trade source amounts missing")
    return output

def inspect(con,expected_commit):
    packets=con.execute(f"""SELECT build_id,source_git_commit,source_kind,source_url,
        source_http_received_at,original_payload_sha256,original_html,
        parsed_observation_count,warehouse_ingested_at,
        provider_first_publication_verified,original_revision_vintage_verified,
        pre_event_consensus_verified,redistribution_rights_approved,
        institutional_event_model_approved,source_status
        FROM {P}lab_bea_original_release_page_receipts_v1
        ORDER BY source_kind""").fetchall()
    values=con.execute(f"""SELECT build_id,source_kind,original_payload_sha256,
        reported_period,reported_metric,reported_value,prior_month_value,
        reported_unit,source_http_received_at,warehouse_ingested_at,
        publisher_first_known_at,verified_announcement_surprise,
        original_provider_first_release_certified,survey_consensus_asof_verified,
        licensed_downstream_use,institutional_model_approved
        FROM {P}lab_bea_original_reported_values_v1""").fetchall()
    if len(packets)!=2 or len(values)!=10:
        raise ValueError("BEA original-page packet or ten measurement row count drift")
    original={}
    build_ids=set()
    for p in packets:
        (build,commit,kind,url,received,sha,raw,n,ingested,
         pit,revision,consensus,rights,beta,status)=p
        if (commit!=expected_commit or kind not in SOURCE_URL or kind in original
            or url!=SOURCE_URL[kind] or not isinstance(received,datetime)
            or received.tzinfo is None or not isinstance(ingested,datetime)
            or ingested.tzinfo is None or not received<=ingested
            or hashlib.sha256(raw).hexdigest()!=sha
            or status!="ORIGINAL_BEA_RELEASE_PAGE_RETRIEVED_LATER_NOT_FIRST_PUBLICATION"
            or any(x is not False for x in (pit,revision,consensus,rights,beta))):
            raise ValueError("Original BEA immutable payload/source rights/PIT invalid")
        computed=compute_independent(raw,kind)
        if len(computed)!=n:
            raise ValueError("Original BEA packet documented observation count drift")
        original[kind]=(sha,received,ingested,computed)
        build_ids.add(build)
    if set(original)!=set(SOURCE_URL) or len(build_ids)!=1:
        raise ValueError("Not exactly two official original BEA source kinds from one build")
    seen=set()
    for v in values:
        (build,kind,sha,period,metric,actual,prior,unit,
         received,ingested,published,surprise,pit,consensus,rights,beta)=v
        key=(kind,metric)
        if (build not in build_ids or kind not in original or key in seen
            or period!="2026-08" or any(x is not False for x in (pit,consensus,rights,beta))
            or published is not None or surprise is not None
            or sha!=original[kind][0] or received!=original[kind][1]
            or ingested!=original[kind][2] or metric not in original[kind][3]):
            raise ValueError("Forged or unlinked BEA report/first-release/rights row")
        exp_unit,exp_value,exp_prior=original[kind][3][metric]
        if (unit!=exp_unit or not isinstance(actual,(float,int))
            or not math.isclose(actual,exp_value,rel_tol=0,abs_tol=1e-10)
            or (exp_prior is None and prior is not None)
            or (exp_prior is not None and (prior is None or not math.isclose(prior,exp_prior,rel_tol=0,abs_tol=1e-10)))):
            raise ValueError("BEA published original value or native unit drift")
        seen.add(key)
    if seen!={(k,m) for k,(_,_,_,d) in original.items() for m in d}:
        raise ValueError("Missing authentic original source observation")
    return {
        "status":"ORIGINAL_BEA_REPORTED_VALUES_AND_HTML_RECEIPT_REPLAY_VERIFIED_RESEARCH_ONLY",
        "build_id":next(iter(build_ids)),"original_source_html_packets":2,
        "native_reported_value_cells":10,"period":"2026-08",
        "original_source_packet_sha256":{k:v[0] for k,v in original.items()},
        "historical_publisher_first_known_verified":False,
        "pre_event_consensus_survey_verified":False,
        "source_redistribution_rights_verified":False,
        "institutional_event_factor_beta_approved":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--producer-source-commit",required=True)
    args=p.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}",args.producer_source_commit):
        raise ValueError("Exact reviewed BEA producer SHA required")
    with duckdb.connect("md:eventrisk_factor_lab?attach_mode=single") as c:
        c.execute("SET TimeZone='UTC'")
        result=inspect(c,args.producer_source_commit)
    print(json.dumps(result,sort_keys=True,default=str))
    print("INDEPENDENT_BEA_10_ACTUAL_REPORTED_VALUES_SOURCE_QA=PASS",flush=True)

if __name__=="__main__":
    main()
