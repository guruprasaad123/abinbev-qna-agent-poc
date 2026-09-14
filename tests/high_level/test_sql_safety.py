"""
High-Level Test Suite: 03. SQL Safety & Security Controls
Covers Attribute 9:
- Read-only SQLite enforcement
- Single-statement SELECT-only validation
- Table whitelist enforcement
- Disallowed SQL keywords (DROP, DELETE, UPDATE, INSERT, ALTER, ATTACH, PRAGMA)
- Row cap enforcement (LIMIT 500)
- SQL injection pattern prevention
"""
import unittest
from src.tools.sql_tool import run_query, validate_sql, SQLSafetyError, ALLOWED_TABLES


class TestSQLSafety(unittest.TestCase):
    # --- Valid Query Executions ---
    def test_01_valid_simple_select(self):
        r = run_query("SELECT brand, country, year FROM fact_monthly_kpi LIMIT 10")
        self.assertGreater(r.row_count, 0)
        self.assertLessEqual(r.row_count, 10)

    def test_02_valid_group_by_brand(self):
        r = run_query("SELECT brand, SUM(net_revenue_usd) AS rev FROM fact_monthly_kpi GROUP BY brand")
        self.assertGreater(r.row_count, 0)
        self.assertIn("rev", r.columns)

    def test_03_valid_group_by_country_and_year(self):
        r = run_query("SELECT country, year, SUM(volume) AS vol FROM fact_monthly_kpi GROUP BY country, year")
        self.assertGreater(r.row_count, 0)
        self.assertIn("vol", r.columns)

    def test_04_valid_where_clause_with_quotes(self):
        r = run_query("SELECT * FROM fact_monthly_kpi WHERE brand = 'Budweiser' AND country = 'United States' LIMIT 5")
        self.assertGreater(r.row_count, 0)
        self.assertLessEqual(r.row_count, 5)

    def test_05_valid_dim_brand_lookup(self):
        r = run_query("SELECT brand, category, sub_category FROM dim_brand")
        self.assertGreater(r.row_count, 0)
        self.assertIn("brand", r.columns)

    def test_06_valid_dim_geo_lookup(self):
        r = run_query("SELECT country, region FROM dim_geo")
        self.assertGreater(r.row_count, 0)
        self.assertIn("region", r.columns)

    def test_07_valid_join_between_allowed_tables(self):
        sql = ("SELECT f.brand, d.category, SUM(f.net_revenue_usd) AS rev "
               "FROM fact_monthly_kpi f JOIN dim_brand d ON f.brand = d.brand "
               "GROUP BY f.brand, d.category")
        r = run_query(sql)
        self.assertGreater(r.row_count, 0)
        self.assertIn("category", r.columns)

    # --- Row Cap Enforcement ---
    def test_08_row_cap_appended_when_missing(self):
        safe = validate_sql("SELECT brand FROM fact_monthly_kpi")
        self.assertIn("LIMIT 500", safe)

    def test_09_row_cap_lowered_when_excessive(self):
        safe = validate_sql("SELECT brand FROM fact_monthly_kpi LIMIT 10000")
        self.assertIn("LIMIT 500", safe)

    def test_10_row_cap_respected_when_smaller(self):
        safe = validate_sql("SELECT brand FROM fact_monthly_kpi LIMIT 25")
        self.assertIn("LIMIT 25", safe)

    # --- Single-Statement Enforcement ---
    def test_11_block_stacked_semicolon(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; SELECT * FROM dim_brand")

    def test_12_block_stacked_drop_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; DROP TABLE fact_monthly_kpi;")

    def test_13_block_stacked_delete(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; DELETE FROM fact_monthly_kpi WHERE 1=1;")

    # --- Data Modification Disallowed ---
    def test_14_block_drop_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("DROP TABLE fact_monthly_kpi")

    def test_15_block_delete_from(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("DELETE FROM fact_monthly_kpi WHERE brand='Budweiser'")

    def test_16_block_update_set(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("UPDATE fact_monthly_kpi SET net_revenue_usd = 0")

    def test_17_block_insert_into(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("INSERT INTO fact_monthly_kpi (brand) VALUES ('FakeBrand')")

    def test_18_block_alter_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("ALTER TABLE fact_monthly_kpi ADD COLUMN hacked TEXT")

    def test_19_block_create_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("CREATE TABLE evil (id INT)")

    # --- Administrative & System Commands Disallowed ---
    def test_20_block_pragma(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("PRAGMA table_info(dim_brand)")

    def test_21_block_attach_database(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("ATTACH DATABASE '/tmp/evil.db' AS evil")

    def test_22_block_vacuum(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("VACUUM")

    # --- Table Whitelist Enforcement ---
    def test_23_block_sqlite_master(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT name FROM sqlite_master")

    def test_24_block_sqlite_sequence(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM sqlite_sequence")

    def test_25_block_arbitrary_unauthorized_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM users")

    def test_26_block_unauthorized_passwords_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM passwords")

    # --- Non-SELECT and Comment Injection Attempts ---
    def test_27_block_empty_query(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("")

    def test_28_block_comment_only(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("-- just a comment")

    def test_29_block_inline_comment_evasion(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql("SELECT * FROM fact_monthly_kpi; -- DROP TABLE dim_brand;")

    def test_30_allowed_tables_match_schema(self):
        self.assertIn("fact_monthly_kpi", ALLOWED_TABLES)
        self.assertIn("dim_brand", ALLOWED_TABLES)
        self.assertIn("dim_geo", ALLOWED_TABLES)

    def test_31_run_query_returns_error_on_invalid_sql(self):
        with self.assertRaises(SQLSafetyError):
            run_query("SELECT non_existent_column FROM fact_monthly_kpi")

    def test_32_run_query_blocks_injection_safely(self):
        with self.assertRaises(SQLSafetyError):
            run_query("DROP TABLE fact_monthly_kpi")


if __name__ == "__main__":
    unittest.main()
