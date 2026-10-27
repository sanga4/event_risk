"""Security regression tests: standard MotherDuck PAT may have WRITE privileges.
No application query may reach that PAT unless parsed as a single SELECT."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class StandardMotherDuckTokenGuardTests(unittest.TestCase):
    def test_legitimate_selects(self):
        statements=[
            "SELECT 1",
            "SELECT * FROM main.lab_factor_catalog LIMIT 5",
            """WITH latest AS (SELECT factor_id FROM main.lab_factor_catalog)
               SELECT COUNT(*) FROM latest""",
            """SELECT table_name,column_name,data_type,ordinal_position
               FROM information_schema.columns
               WHERE table_catalog=current_database() AND table_schema='main'
               LIMIT 4000""",
            """SELECT 'graph_question_nodes' metric, COUNT(*) value FROM main.graph_nodes
               UNION ALL SELECT 'graph_edges_versioned_records' metric, COUNT(*) value
               FROM main.graph_edges""",
        ]
        for sql in statements:
            with self.subTest(sql=sql[:70]):
                self.assertTrue(app._assert_read_query(sql))

    def test_mutations_and_multistatements_rejected(self):
        statements=[
            "DROP TABLE main.graph_nodes",
            "DELETE FROM main.graph_edges",
            "UPDATE main.lab_factor_catalog SET factor_id='oops'",
            "INSERT INTO main.lab_factor_catalog VALUES ('unsafe')",
            "ALTER TABLE main.graph_nodes DROP COLUMN node_id",
            "CREATE TABLE main.evil AS SELECT 1",
            "ATTACH 'external.db' AS ext",
            "COPY (SELECT 1) TO '/tmp/escape.csv'",
            "SELECT 1; DELETE FROM main.graph_nodes",
            "WITH a AS (SELECT 1) SELECT * FROM a; DROP TABLE graph_edges",
            "SET TimeZone='America/New_York'",
            "PRAGMA version",
            "CALL something()",
        ]
        for sql in statements:
            with self.subTest(sql=sql[:70]):
                with self.assertRaises(Exception):
                    app._assert_read_query(sql)

    def test_dynamic_external_readers_rejected(self):
        statements=[
            "SELECT * FROM read_csv('s3://secret-bucket/keys.csv')",
            "SELECT * FROM read_parquet('https://example.com/data.parquet')",
            "SELECT * FROM read_json('secrets.json')",
            "SELECT * FROM query('DROP TABLE main.graph_nodes')",
            "SELECT * FROM sqlite_scan('local.db','secrets')",
            "SELECT current_setting('motherduck_token')",
        ]
        for sql in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(Exception):
                    app._assert_read_query(sql)

    def test_error_before_any_query_or_connection(self):
        # A missing credential must fail closed, not connect or execute.
        import os
        from unittest import mock
        with mock.patch.dict(os.environ,{"MOTHERDUCK_TOKEN":"synthetic-never-real"},clear=True):
            with self.assertRaises(ValueError):
                app._db_query("DELETE FROM main.graph_nodes")

if __name__=="__main__":
    unittest.main()
