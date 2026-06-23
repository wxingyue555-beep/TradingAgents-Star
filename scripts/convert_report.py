#!/usr/bin/env python3
"""Convert TradingAgents HTML report to Markdown."""
import re
from html.parser import HTMLParser

HTML_PATH = "report/603218.SH/report_2026-06-23.html"
MD_PATH = "report/603218.SH/report_2026-06-23.md"

class ReportConverter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lines = []
        self.current = ""
        self.in_style = False
        self.in_script = False
        self.in_section_body = False
        self.section_title = ""
        self.table_buf = []
        self.row_cells = []
        self.in_title = False
        self.title_text = False
        self.badge_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "style":
            self.in_style = True; return
        if tag == "script":
            self.in_script = True; return
        if self.in_style or self.in_script:
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self.flush()
            level = int(tag[1])
            self.current = "#" * level + " "
        elif tag == "p":
            self.flush()
        elif tag == "br":
            self.current += "\n"
        elif tag == "li":
            self.flush()
            self.current = "- "
        elif tag == "strong":
            self.current += "**"
        elif tag == "em":
            self.current += "*"
        elif tag == "code":
            self.current += "`"
        elif tag == "pre":
            self.flush()
            self.current = "\n```\n"
        elif tag == "table":
            self.flush()
            self.table_buf = []
        elif tag == "tr":
            self.row_cells = []
        elif tag == "th" or tag == "td":
            self.current = ""
        elif tag == "div":
            cls = attrs_dict.get("class", "")
            if "section-header" in cls:
                self.section_title = ""
            elif "badge" in cls:
                for part in cls.split():
                    if part.startswith("badge-"):
                        self.badge_text = part.replace("badge-", "")
        elif tag == "span":
            cls = attrs_dict.get("class", "")
            if "badge" in cls:
                for part in cls.split():
                    if part.startswith("badge-"):
                        self.badge_text = part.replace("badge-", "")
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False; return
        if tag == "script":
            self.in_script = False; return
        if self.in_style or self.in_script:
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self.flush()
            self.lines.append("")
        elif tag == "p":
            self.flush()
            self.lines.append("")
        elif tag == "strong":
            self.current += "**"
        elif tag == "em":
            self.current += "*"
        elif tag == "code":
            self.current += "`"
        elif tag == "pre":
            self.current += "\n```"
            self.flush()
            self.lines.append("")
        elif tag == "table":
            self._dump_table()
        elif tag == "th" or tag == "td":
            cell = self.current.strip()
            self.row_cells.append(cell)
            self.current = ""
        elif tag == "tr":
            if self.row_cells:
                self.table_buf.append(self.row_cells)
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_style or self.in_script or self.in_title:
            return
        self.current += data

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.current += "\n"
        elif tag == "hr":
            self.flush()
            self.lines.append("---")

    def flush(self):
        text = self.current.strip()
        if text:
            # Collapse internal newlines
            text = re.sub(r'\n{2,}', '\n\n', text)
            self.lines.append(text)
        self.current = ""

    def _dump_table(self):
        if not self.table_buf or len(self.table_buf) < 1:
            return
        header = self.table_buf[0]
        self.lines.append("| " + " | ".join(header) + " |")
        self.lines.append("|" + "|".join("---" for _ in header) + "|")
        for row in self.table_buf[1:]:
            while len(row) < len(header):
                row.append("")
            self.lines.append("| " + " | ".join(row) + " |")
        self.lines.append("")


def main():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    converter = ReportConverter()
    converter.feed(html)

    # Clean consecutive blanks and remove UI artifacts
    clean = []
    prev = True
    icons = {"▼", "▶", "📈", "📰", "🏭", "💰", "📊", "🌐", "🛡️", "📋", "📡"}
    for line in converter.lines:
        text = line.strip()
        # Skip UI-only lines (icons, whitespace)
        if not text or text in icons or (len(text) <= 2 and not text.isascii()):
            if not prev:
                prev = True
                continue
            continue
        # Fix double-space in markdown headers
        if text.startswith("#") and text.startswith("# "):
            pass  # already correct
        elif text.startswith("#  "):
            text = text.replace("#  ", "# ", 1)
        if prev and not text:
            continue
        clean.append(text)
        prev = (text == "")

    # Add decision badge at top if found
    if converter.badge_text:
        badge_map = {"buy": "买入", "sell": "卖出", "hold": "持有", "overweight": "增持", "underweight": "减持"}
        label = badge_map.get(converter.badge_text, converter.badge_text)
        clean.insert(0, f"**决策: {label}**")
        clean.insert(1, "")

    md = "\n".join(clean).strip()
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ 转换完成: {MD_PATH}")
    print(f"   行数: {len(clean)}, 字符: {len(md)}")


if __name__ == "__main__":
    main()
