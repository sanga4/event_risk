"""Bounded full research-warehouse browser for an explicitly authorized data admin.

The browser never receives database credentials or executes user SQL.
A dedicated MotherDuck read-scaling identity must be granted only approved data.
All datasets are enumerated from the protected account's information schema.
"""
from __future__ import annotations
import re

_NAME=re.compile(r"^(?:lab_[a-z0-9_]+|graph_nodes|graph_edges)$")
_PRIVATE_COLUMN=re.compile(r"(?:password|secret|access_token|api_key|private_key|bearer_token)",re.I)
MAX_ROWS=50
MAX_OFFSET=10000

def classification(name):
    if name in ("graph_nodes","graph_edges") or name.startswith(
       ("lab_live_","lab_market_","lab_mapping_","lab_capture_")):
        return "SOURCE_REDISPLAY"
    if name=="lab_factor_catalog":return "FACTOR_METADATA"
    return "DERIVED_RESEARCH"

def allowed_table_name(name):
    return bool(_NAME.fullmatch(name)) and len(name)<=110

def describe(query,table=""):
    if table and not allowed_table_name(table):
        raise ValueError("INVALID_TABLE_NAME")
    rows=query("""SELECT table_name,column_name,data_type,ordinal_position
              FROM information_schema.columns
              WHERE table_catalog=current_database() AND table_schema='main'
                AND (table_name LIKE 'lab_%' OR table_name IN ('graph_nodes','graph_edges'))
              ORDER BY table_name,ordinal_position
              LIMIT 4000""")
    discovered={}
    for r in rows:
        name=r["table_name"]
        if not allowed_table_name(name):continue
        item=discovered.setdefault(name,{"name":name,"kind":classification(name),
            "columns":[],"schema":"main","permissions":"RESTRICTED_AUTHORIZATION_REQUIRED"})
        col=r["column_name"]
        if not _PRIVATE_COLUMN.search(col):
            item["columns"].append({"name":col,"type":r["data_type"]})
    items=[v for v in discovered.values() if v["columns"]]
    if table:return next((v for v in items if v["name"]==table),None)
    return items

def explore(query,resource,params,source_approved=False,derived_approved=False):
    table=str(params.get("table",[""])[0]).strip()
    if resource=="datasets":
        items=describe(query)
        return {"mode":"LIVE_MOTHERDUCK_CATALOG","database":"eventrisk_factor_lab",
            "tables":items,"table_count":len(items),
            "all_tables_have_independent_rights_gates":True,
            "arbitrary_sql_allowed":False}
    if resource not in ("table","columns"):
        raise ValueError("UNKNOWN_WAREHOUSE_RESOURCE")
    item=describe(query,table)
    if item is None:raise ValueError("UNKNOWN_DATASET_OR_NO_SAFE_COLUMNS")
    if resource=="columns":
        return {"mode":"LIVE_MOTHERDUCK_DATASET_METADATA","dataset":item}
    group=item["kind"]
    if group=="SOURCE_REDISPLAY" and not source_approved:
        raise PermissionError("SOURCE_DATA_ENTITLEMENT_REQUIRED")
    if group=="DERIVED_RESEARCH" and not derived_approved:
        raise PermissionError("DERIVED_DATA_ENTITLEMENT_REQUIRED")
    if group=="FACTOR_METADATA" and not derived_approved:
        raise PermissionError("DATA_ADMIN_RESEARCH_ENTITLEMENT_REQUIRED")
    try:
        limit=int(params.get("limit",["25"])[0])
        offset=int(params.get("offset",["0"])[0])
    except (ValueError,TypeError,IndexError):
        raise ValueError("INVALID_PAGINATION")
    if limit<1 or limit>MAX_ROWS or offset<0 or offset>MAX_OFFSET:
        raise ValueError("PAGINATION_OUT_OF_BOUNDS")
    columns=[x["name"] for x in item["columns"]][:28]
    if not columns:raise ValueError("NO_PERMITTED_COLUMNS")
    # Names are taken from information_schema and double-quoted, not from
    # caller input. Only page values are parameters. No SELECT *.
    safe_cols=",".join('"'+x.replace('"','""')+'"' for x in columns)
    sql=f'SELECT {safe_cols} FROM main."{table}" LIMIT ? OFFSET ?'
    raw=query(sql,(limit,offset))
    rows=[]
    for r in raw:
        row={}
        for c in columns:
            value=r.get(c)
            if isinstance(value,(dict,list)):
                import json
                value=json.dumps(value,default=str)
            elif not isinstance(value,(str,int,float,bool,type(None))):
                value=str(value)
            if isinstance(value,str) and len(value)>2000:
                value=value[:2000]+"… [TRUNCATED]"
            row[c]=value
        rows.append(row)
    return {"mode":"LIVE_MOTHERDUCK_ADMIN_READ_ONLY_PAGE",
        "dataset":item,"columns":columns,"rows":rows,"limit":limit,"offset":offset,
        "returned":len(rows),"has_next_page":len(rows)==limit,
        "rights_scope":group,"no_arbitrary_sql":True,
        "provenance_warning":"Records may be revised or lack publisher-original PIT; not certified investment signals."}
