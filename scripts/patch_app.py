#!/usr/bin/env python3
"""Patch app.py to support order_by in /api/news/query"""
path = '/Users/star_mac/gupiao/sql_db/app.py'
with open(path, 'r') as f:
    text = f.read()

old = '    keyword = request.args.get("q", "").strip() or None\n    try:'
new = '    keyword = request.args.get("q", "").strip() or None\n    order_by = request.args.get("order_by", "").strip() or None\n    try:'
text = text.replace(old, new)

old2 = '        date=date, code=code, category=category, keyword=keyword,\n        limit=limit, offset=offset,'
new2 = '        date=date, code=code, category=category, keyword=keyword,\n        order_by=order_by,\n        limit=limit, offset=offset,'
text = text.replace(old2, new2)

with open(path, 'w') as f:
    f.write(text)

print("✅ app.py patched: order_by support added")
