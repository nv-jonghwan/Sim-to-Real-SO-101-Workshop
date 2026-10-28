"""Translate embedded explanations that Sphinx gettext cannot reach.

The catalog is scoped to exact source fragments. Stale fragments fail the
build; replacements are simultaneous so translations cannot cascade.
"""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import re

from docutils import nodes
from sphinx.errors import SphinxError


def catalog_path(app):
    return Path(app.srcdir) / "locale/ko/interactive.json"


def pattern(entry):
    escaped = re.escape(entry["source"])
    return rf"(?<=>){escaped}(?=<)" if entry["mode"] == "html" else escaped


def translate(source, entries):
    if not entries:
        return source
    entries = sorted(entries, key=lambda e: len(e["source"]), reverse=True)
    replacements = {e["source"]: e["translation"] for e in entries}
    expression = "|".join(pattern(e) for e in entries)
    return re.sub(expression, lambda match: replacements[match.group()], source)


def load_catalog(srcdir):
    """Validate original fragments, protected code/links and catalog paths."""
    root = Path(srcdir).resolve()
    data = json.loads((root / "locale/ko/interactive.json").read_text())
    if data.get("version") != 1:
        raise SphinxError("Unsupported interactive translation catalog version")
    for name, entries in data["files"].items():
        path = root / name
        if (not path.resolve().is_relative_to(root)
                or not name.startswith(("_static/", "_includes/"))
                or path.suffix not in (".html", ".js")):
            raise SphinxError(f"Invalid interactive translation path: {name}")
        source = path.read_text()
        seen = set()
        for entry in entries:
            if (entry.get("mode") not in ("html", "literal")
                    or not entry.get("source") or not entry.get("translation")
                    or entry["source"] in seen):
                raise SphinxError(f"Invalid/duplicate interactive translation: {name}")
            seen.add(entry["source"])
            if not re.search(pattern(entry), source):
                raise SphinxError(
                    f"Stale interactive translation in {name}: {entry['source'][:100]}"
                )
        rendered = translate(source, entries)
        for expression in (
            r"<code\b[^>]*>.*?</code>", r"<pre\b[^>]*>.*?</pre>",
            r'\b(?:href|src|id|data-term|data-definition)="[^"]*"',
        ):
            if Counter(re.findall(expression, source, re.S)) != Counter(
                re.findall(expression, rendered, re.S)
            ):
                raise SphinxError(f"Protected interactive content changed: {name}")
    return data["files"]


def configure(app, config):
    if config.language == "ko":
        # Catalog edits invalidate cached doctrees on incremental builds.
        config.course_interactive_digest = sha256(catalog_path(app).read_bytes()).hexdigest()


def prepare(app):
    if app.config.language == "ko" and app.builder.format == "html":
        app._course_interactive_catalog = load_catalog(app.srcdir)


def raw_html(app, doctree, docname):
    catalog = getattr(app, "_course_interactive_catalog", {})
    entries = {}
    for name, messages in catalog.items():
        if name.startswith("_includes/"):
            for entry in messages:
                entries[(entry["source"], entry["mode"])] = entry
    for node in doctree.findall(nodes.raw):
        if "html" not in node.get("format", "").split():
            continue
        original = node.astext()
        translated = translate(original, list(entries.values()))
        if original != translated:
            node.children = []
            node += nodes.Text(translated)


def static_assets(app, exception):
    if exception is not None:
        return
    for name, entries in getattr(app, "_course_interactive_catalog", {}).items():
        if name.startswith("_static/"):
            source = (Path(app.srcdir) / name).read_text()
            target = Path(app.outdir) / name
            target.write_text(translate(source, entries))


def setup(app):
    app.add_config_value("course_interactive_digest", "", "env")
    app.connect("config-inited", configure)
    app.connect("builder-inited", prepare)
    app.connect("doctree-resolved", raw_html)
    app.connect("build-finished", static_assets)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
