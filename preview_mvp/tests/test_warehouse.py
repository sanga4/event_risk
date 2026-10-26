import importlib.util
from pathlib import Path
from unittest import TestCase, mock
import os

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("eventrisk_warehouse",ROOT/"warehouse.py")
warehouse=importlib.util.module_from_spec(spec)
spec.loader.exec_module(warehouse)

def columns():
    rows=[]
    for table,coltype in [
      ("lab_factor_catalog",[("factor_id","VARCHAR"),("name","VARCHAR"),("secret_token","VARCHAR")]),
      ("lab_factor_observations",[("factor_id","VARCHAR"),("observed_date","DATE"),("value","DOUBLE")]),
      ("graph_nodes",[("node_id","VARCHAR"),("name","VARCHAR")]),
      ("not_an_allowed_table",[("password","VARCHAR")])
    ]:
        for i,(name,typ) in enumerate(coltype):
            rows.append({"table_name":table,"column_name":name,
                         "data_type":typ,"ordinal_position":i+1})
    return rows

class TestFullWarehouseExplorer(TestCase):
    def test_metadata_from_live_catalog_and_sensitive_column_block(self):
        query=mock.Mock(return_value=columns())
        items=warehouse.describe(query)
        self.assertEqual({x["name"] for x in items},
          {"lab_factor_catalog","lab_factor_observations","graph_nodes"})
        self.assertEqual([c["name"] for c in next(x for x in items if x["name"]=="lab_factor_catalog")["columns"]],
          ["factor_id","name"])
        self.assertEqual(len(query.call_args.args),1)
        self.assertIn("information_schema.columns",query.call_args.args[0])
    def test_sql_cannot_be_supplied_by_browser(self):
        for name in ['graph_nodes;DROP TABLE graph_edges','lab_bad"','../env','lab_Password']:
            self.assertFalse(warehouse.allowed_table_name(name),name)
    def test_dataset_page_has_strict_bounds(self):
        calls=[]
        def fake(sql,params=()):
            calls.append((sql,params))
            return columns() if "information_schema" in sql else [
               {"factor_id":"DGS2","observed_date":"2026-10-23","value":4.1}]
        bad={"table":["lab_factor_observations"],"limit":["51"]}
        with self.assertRaisesRegex(ValueError,"PAGINATION"):
            warehouse.explore(fake,"table",bad,derived_approved=True)
        with self.assertRaisesRegex(PermissionError,"DERIVED"):
            warehouse.explore(fake,"table",{"table":["lab_factor_observations"]})
        good=warehouse.explore(fake,"table",{"table":["lab_factor_observations"],"limit":["1"],
                      "offset":["10"]},derived_approved=True)
        self.assertEqual(good["rows"][0]["factor_id"],"DGS2")
        self.assertIn('FROM main."lab_factor_observations"',calls[-1][0])
        self.assertEqual(calls[-1][1],(1,10))
        self.assertNotIn("secret_token",good["columns"])
    def test_source_derived_rights_are_independent(self):
        fake=mock.Mock(return_value=columns())
        with self.assertRaisesRegex(PermissionError,"SOURCE"):
            warehouse.explore(fake,"table",{"table":["graph_nodes"]},derived_approved=True)
        with self.assertRaisesRegex(PermissionError,"DERIVED"):
            warehouse.explore(fake,"table",{"table":["lab_factor_observations"]},source_approved=True)
    def test_public_catalog_discovery_is_not_data_exfiltration(self):
        result=warehouse.explore(mock.Mock(return_value=columns()),"datasets",{})
        self.assertFalse(result["arbitrary_sql_allowed"])
        self.assertEqual(result["table_count"],3)
        self.assertEqual(result["mode"],"LIVE_MOTHERDUCK_CATALOG")
