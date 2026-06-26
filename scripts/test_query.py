import sqlite3
from pathlib import Path
db_path = Path('/Users/star_mac/Documents/GitHub/TradingAgents-Star/tradingagents/dataflows/news.db')
print(f"path={db_path}, exists={db_path.exists()}")
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.execute("PRAGMA query_only=TRUE")
conn.row_factory = sqlite3.Row
total = conn.execute("SELECT COUNT(*) FROM news WHERE code = '603023'").fetchone()[0]
print(f"total for 603023: {total}")
rows = conn.execute("SELECT id, date, code, stock_name, category, title FROM news WHERE code = '603023' ORDER BY date DESC LIMIT 3").fetchall()
for r in rows:
    print(dict(r))
conn.close()
print("OK")
