#!/usr/bin/env python3
"""Convert the Fedlex Akoma Ntoso XML files downloaded by fetch.py into Markdown.

Usage: convert.py [RAW_DIR] [OUT_DIR] [--langs de,fr,it,rm] [--retrieved YYYY-MM-DD]
       (defaults: ../../_raw/ch and the repository root)

Layout: <lang>/<d1>/<d1d2>/<sr>-<slug>.md            internal law, e.g. de/2/21/210-zgb.md
        <lang>/0/0.<d1>/0.<d1d2>/<sr>-<slug>.md      international law, e.g. de/0/0.1/0.10/0.101-emrk.md
"""
import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

from lxml import etree

AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
FEDLEX = "http://fedlex.admin.ch/"

# Fedlex resource-type id -> LawCodex type
TYPES = {
    "10": "constitution", "16": "cantonal_constitution",
    "21": "act", "22": "act",
    "29": "ordinance", "26": "ordinance", "27": "ordinance", "28": "ordinance",
    "1": "ordinance", "2": "ordinance", "3": "ordinance", "4": "ordinance", "5": "ordinance",
    "7": "federal_decree", "8": "federal_decree", "9": "federal_decree", "36": "federal_decree",
    "15": "agreement", "31": "treaty", "32": "treaty",
}
CODES = {"210", "220", "311.0", "312.0", "272", "281.1", "321.0", "173.110"}

CONTAINERS = {"book", "part", "title", "subtitle", "chapter", "subchapter", "section",
              "subsection", "subdivision", "level", "division", "proviso", "transitional",
              "hcontainer", "tome", "clause"}


def ln(el):
    t = el.tag
    if not isinstance(t, str):
        return None
    return t.split("}", 1)[1] if "}" in t else t


def slugify(s, maxlen=70):
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def ws(s):
    return re.sub(r"[ \t\r\n\u00a0]+", " ", s)


class Conv:
    def __init__(self):
        self.notes = []
        self.lines = []

    # ---------- inline ----------
    def inline(self, el, ctx="p"):
        """Return Markdown text for el's content (not including el's tail)."""
        out = [ws(el.text or "")]
        for ch in el:
            out.append(self.inline_el(ch, ctx))
            out.append(ws(ch.tail or ""))
        return "".join(out)

    def inline_el(self, el, ctx):
        n = ln(el)
        if n is None:
            return ""
        if n == "authorialNote":
            txt = " ".join(t for t in (self.inline(p, "note").strip() for p in el) if t)
            if not len(el):
                txt = self.inline(el, "note").strip()
            self.notes.append(txt)
            return f"[^{len(self.notes)}]"
        if n == "br":
            return "<br>" if ctx in ("cell", "head") else ("  \n" if ctx == "p" else " ")
        inner = self.inline(el, ctx)
        if n == "b":
            return wrap(inner, "**")
        if n == "i":
            return wrap(inner, "*")
        if n in ("sup", "sub", "u"):
            if re.fullmatch(r"(\[\^\d+\])+", inner.strip()):
                return inner.strip()
            return f"<{n}>{inner.strip()}</{n}>" if inner.strip() else inner
        if n == "ref":
            href = el.get("href")
            if href and inner.strip() and ctx != "head":
                return f"[{inner.strip()}]({href})" + (" " if inner.endswith(" ") else "")
            return inner
        if n == "img":
            src = el.get("src", "")
            return f"![{el.get('alt', '')}]({src})"
        if n in ("p", "block", "blockList", "item", "content", "table"):
            # block inside inline context (rare): flatten
            return " " + self.flat(el, ctx) + " "
        return inner

    def flat(self, el, ctx):
        if ln(el) == "table":
            return self.flat_text(el)
        return self.inline(el, ctx).strip()

    def flat_text(self, el):
        return ws(" ".join(el.itertext())).strip()

    # ---------- blocks ----------
    def emit(self, s=""):
        self.lines.append(s)

    def para(self, text):
        text = text.strip()
        if text:
            if re.match(r"^(#|>|[-+*] |\d+[.)] )", text):
                text = "\\" + text
            self.emit(text)
            self.emit()

    def heading_text(self, el):
        parts = []
        num = el.find(f"{{{AKN}}}num")
        head = el.find(f"{{{AKN}}}heading")
        sub = el.find(f"{{{AKN}}}subheading")
        for x in (num, head, sub):
            if x is not None:
                t = self.inline(x, "head").strip()
                if x is num:
                    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t).strip()
                if t:
                    parts.append(t)
        return " ".join(parts)

    def heading(self, level, text):
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return
        if level <= 6:
            self.emit("#" * level + " " + text)
        else:
            self.emit(f"**{text}**")
        self.emit()

    def block(self, el, level, indent=""):
        n = ln(el)
        if n is None:
            return
        if n in ("num", "heading", "subheading"):
            return
        if n in CONTAINERS or n in ("article", "component", "attachment"):
            self.heading(level, self.heading_text(el))
            for ch in el:
                self.block(ch, level + 1, indent)
            return
        if n in ("paragraph", "subparagraph", "point", "alinea"):
            num = el.find(f"{{{AKN}}}num")
            label = self.inline(num, "p").strip() if num is not None else ""
            head = el.find(f"{{{AKN}}}heading")
            if head is not None:
                self.para(f"*{self.inline(head, 'p').strip()}*")
            pending = f"<sup>{label}</sup> " if label else ""
            for ch in el:
                cn = ln(ch)
                if cn in ("num", "heading"):
                    continue
                if pending and cn == "content":
                    kids = [k for k in ch if ln(k)]
                    if kids and ln(kids[0]) == "p":
                        self.para(pending + self.inline(kids[0], "p").strip())
                        kids = kids[1:]
                    else:
                        self.para(pending)
                    pending = ""
                    for k in kids:
                        self.block(k, level, indent)
                elif pending:
                    self.para(pending)
                    pending = ""
                    self.block(ch, level, indent)
                else:
                    self.block(ch, level, indent)
            if pending:
                self.para(pending)
            return
        if n in ("content", "intro", "wrapUp", "mainBody", "body", "preamble", "preface",
                 "conclusions", "container", "doc", "components", "act", "signature",
                 "formula", "longTitle", "citations", "recitals", "recital", "citation",
                 "blockContainer", "attachments"):
            for ch in el:
                self.block(ch, level, indent)
            return
        if n in ("p", "block", "listIntroduction", "listWrapUp", "docTitle"):
            self.para(self.inline(el, "p"))
            return
        if n == "blockList" or n == "list":
            for ch in el:
                cn = ln(ch)
                if cn == "item":
                    self.item(ch, level, indent)
                elif cn in ("listIntroduction", "listWrapUp"):
                    t = self.inline(ch, "p").strip()
                    if t:
                        self.emit(indent + t)
                        self.emit()
                else:
                    self.block(ch, level, indent)
            self.emit()
            return
        if n == "table":
            self.table(el)
            return
        if n in ("meta", "references", "identification"):
            return
        # unknown: treat as paragraph text
        self.para(self.inline(el, "p"))

    def item(self, el, level, indent):
        num = el.find(f"{{{AKN}}}num")
        label = self.inline(num, "p").strip() if num is not None else ""
        if label in ("–", "-", "—", "•", "·", "*"):
            label = ""
        state = {"first": True}
        sub = indent + "  "

        def text(t):
            t = t.strip()
            if not t:
                return
            if state["first"]:
                self.emit(f"{indent}- " + (f"{label} " if label else "") + t)
                state["first"] = False
            else:
                self.emit(sub + t)

        def walk_list(bl):
            for it in bl:
                itn = ln(it)
                if itn == "item":
                    if state["first"]:
                        self.emit(f"{indent}- {label}".rstrip())
                        state["first"] = False
                    self.item(it, level, sub)
                elif itn in ("listIntroduction", "listWrapUp"):
                    text(self.inline(it, "p"))
                elif itn in ("blockList", "list"):
                    walk_list(it)
                elif itn == "table":
                    self.emit()
                    self.table(it)
                elif itn:
                    text(self.inline(it, "p"))

        def walk(node):
            for ch in node:
                cn = ln(ch)
                if cn is None or cn == "num":
                    continue
                if cn in ("content", "intro", "wrapUp"):
                    walk(ch)
                elif cn in ("blockList", "list"):
                    walk_list(ch)
                elif cn == "table":
                    if state["first"]:
                        self.emit(f"{indent}- {label}".rstrip())
                        state["first"] = False
                    self.emit()
                    self.table(ch)
                else:
                    text(self.inline(ch, "p"))

        walk(el)
        if state["first"]:
            self.emit(f"{indent}- {label}".rstrip())

    def cell(self, c):
        parts = []
        for ch in c:
            if ln(ch) in ("p", "block"):
                parts.append(self.inline(ch, "cell").strip())
            elif ln(ch) in ("blockList",):
                for it in ch.iter(f"{{{AKN}}}item"):
                    parts.append(self.flat_text(it))
            elif ln(ch) == "table":
                parts.append(self.flat_text(ch))
            else:
                parts.append(self.inline(ch, "cell").strip())
            if ch.tail and ch.tail.strip():
                parts.append(ws(ch.tail).strip())
        if c.text and c.text.strip():
            parts.insert(0, ws(c.text).strip())
        return "<br>".join(p for p in parts if p)

    def table(self, t):
        rows = [r for r in t.iter(f"{{{AKN}}}tr")]
        if not rows:
            return
        simple = all(c.get("colspan") in (None, "1") and c.get("rowspan") in (None, "1")
                     for r in rows for c in r if ln(c) in ("td", "th")) \
            and not t.findall(f".//{{{AKN}}}table")
        grid = [[self.cell(c) for c in r if ln(c) in ("td", "th")] for r in rows]
        width = max(len(r) for r in grid)
        if simple and width > 0:
            grid = [r + [""] * (width - len(r)) for r in grid]
            esc = [[c.replace("|", "\\|").replace("\n", " ") for c in r] for r in grid]
            has_head = all(ln(c) == "th" for c in rows[0] if ln(c) in ("td", "th"))
            if has_head:
                head, body = esc[0], esc[1:]
            else:
                head, body = [""] * width, esc
            self.emit("| " + " | ".join(head) + " |")
            self.emit("|" + "---|" * width)
            for r in body:
                self.emit("| " + " | ".join(r) + " |")
            self.emit()
            return
        out = ["<table>"]
        for r in rows:
            out.append("<tr>")
            for c in r:
                tag = ln(c)
                if tag not in ("td", "th"):
                    continue
                attrs = "".join(f' {a}="{c.get(a)}"' for a in ("colspan", "rowspan")
                                if c.get(a) not in (None, "1"))
                out.append(f"<{tag}{attrs}>{md_inline_to_html(self.cell(c))}</{tag}>")
            out.append("</tr>")
        out.append("</table>")
        self.emit("\n".join(out))
        self.emit()


def md_inline_to_html(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def wrap(s, mark):
    core = s.strip()
    if not core:
        return s
    lead = " " if s[:1].isspace() else ""
    trail = " " if s[-1:].isspace() else ""
    return f"{lead}{mark}{core}{mark}{trail}"


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def convert_file(path, entry, lang, retrieved):
    tree = etree.parse(str(path))
    root = tree.getroot()
    act = root[0]
    c = Conv()
    title = entry["titles"].get(lang) or entry["titles"].get("de") or entry["sr"]
    title = ws(title).strip()
    c.emit(f"# {title}")
    c.emit()
    for part in act:
        n = ln(part)
        if n == "meta":
            continue
        if n == "preface":
            for p in part:
                t = c.inline(p, "p").strip()
                if t:
                    c.para(t)
            continue
        if n == "components":
            for comp in part:
                for doc in comp:
                    pre = doc.find(f"{{{AKN}}}preface")
                    htxt = []
                    if pre is not None:
                        for p in pre.iter(f"{{{AKN}}}p", f"{{{AKN}}}block"):
                            if any(ln(a) == "authorialNote" for a in p.iterancestors()):
                                continue
                            t = c.inline(p, "head").strip()
                            if t:
                                htxt.append(t)
                    c.heading(2, " ".join(htxt).replace("<br>", " ") or "Anhang")
                    for ch in doc:
                        if ln(ch) in ("meta", "preface"):
                            continue
                        c.block(ch, 3)
            continue
        c.block(part, 2)
    body = "\n".join(c.lines).rstrip() + "\n"
    body = re.sub(r"\n{3,}", "\n\n", body)
    if c.notes:
        body += "\n" + "\n".join(f"[^{i}]: {t}" for i, t in enumerate(c.notes, 1)) + "\n"
    f = entry["files"][lang]
    td = entry.get("td", "").rsplit("/", 1)[-1]
    typ = "code" if entry["sr"] in CODES else TYPES.get(td, "unknown")
    if entry["sr"].startswith("0.") and typ not in ("treaty",):
        typ = "treaty" if typ in ("unknown", "agreement") else typ
    eli_path = entry["eli"].split("fedlex.data.admin.ch/", 1)[1]
    fm = ["---", f"title: {yaml_str(title)}"]
    short = entry["short"].get(lang)
    if short:
        fm.append(f"short_title: {yaml_str(ws(short).strip())}")
    fm += [f'identifier: "SR {entry["sr"]}"',
           f'eli: "{entry["eli"]}"',
           f"type: {typ}",
           "jurisdiction: ch",
           f"language: {lang}"]
    if entry.get("dd"):
        fm.append(f"date: {entry['dd']}")
    if entry.get("eif"):
        fm.append(f"in_force_since: {entry['eif']}")
    fm += [f"last_amended: {f['date']}",
           "status: in_force",
           f'source: "https://www.fedlex.admin.ch/{eli_path}/{lang}"',
           f"retrieved: {retrieved}",
           "---", ""]
    return "\n".join(fm) + body


def out_path(out, lang, entry):
    sr = entry["sr"]
    short = entry["short"].get(lang) or ""
    title = entry["titles"].get(lang) or entry["titles"].get("de") or ""
    base = slugify(short, 40) if short and len(slugify(short)) >= 2 else slugify(title, 70)
    name = f"{sr}-{base}" if base else sr
    name = name[:100].rstrip("-")
    if sr.startswith("0."):
        d = sr[2:].replace(".", "")
        dirs = ["0", "0." + d[:1], "0." + d[:2]]
    else:
        d = sr.replace(".", "")
        dirs = [d[:1], d[:2]]
    return out.joinpath(lang, *dirs, name + ".md")


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="?", default=str(here.parent.parent / "_raw" / "ch"))
    ap.add_argument("out", nargs="?", default=str(here.parent))
    ap.add_argument("--langs", default="de,fr,it,rm")
    ap.add_argument("--retrieved", default=dt.date.today().isoformat())
    ap.add_argument("--only", help="comma-separated SR numbers (debug)")
    args = ap.parse_args()
    raw, out = Path(args.raw), Path(args.out)
    cat = json.loads((raw / "catalog.json").read_text())["entries"]
    only = set(args.only.split(",")) if args.only else None
    sys.path.insert(0, str(here))
    from fetch import local_path  # noqa: E402
    ok = missing = err = 0
    for lang in args.langs.split(","):
        for e in cat:
            if only and e["sr"] not in only:
                continue
            if lang not in e["files"]:
                continue
            src = local_path(raw, lang, e)
            if not src.exists():
                missing += 1
                continue
            try:
                md = convert_file(src, e, lang, args.retrieved)
            except Exception as ex:  # keep going, report
                print(f"ERROR {lang} SR {e['sr']}: {ex}", file=sys.stderr)
                err += 1
                continue
            dest = out_path(out, lang, e)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(md, encoding="utf-8")
            ok += 1
    print(f"converted {ok}, missing {missing}, errors {err}", file=sys.stderr)


if __name__ == "__main__":
    main()
