import sqlite3
import sys

path = '/Users/star_mac/gupiao/sql_db/news.db'

# Test 1: direct connect
try:
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"direct OK: {tables}")
    conn.close()
except Exception as e:
    print(f"direct FAIL: {e}")

# Test 2: URI mode
try:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"URI OK: {tables}")
    conn.close()
except Exception as e:
    print(f"URI FAIL: {e}")

# Test 3: URI with cache=shared
try:
    conn = sqlite3.connect(f"file:{path}?mode=ro&cache=shared", uri=True)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"URI+cache OK: {tables}")
    conn.close()
except Exception as e:
    print(f"URI+cache FAIL: {e}")
