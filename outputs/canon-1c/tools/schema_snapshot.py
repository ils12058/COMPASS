"""Snapshot and compare the PostgreSQL schema of two disposable COMPASS databases.

CANON-1C evidence tool. It reads ``pg_catalog`` only (no writes) and is never run against a live
database. Usage, from ``be/`` so the project's psycopg is importable:

    uv run --offline python ../outputs/canon-1c/tools/schema_snapshot.py snapshot \
        --dsn postgresql://compass:...@127.0.0.1:55432/canon_ref_a --out ref-a.json
    uv run --offline python ../outputs/canon-1c/tools/schema_snapshot.py compare ref-a.json ref-b.json

The snapshot keeps every object by name *and* a name-independent signature, so a constraint or
index whose generated name differs between two histories is reported as "renamed", not as a
removal plus an addition.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import psycopg

TABLES = """
SELECT c.relname
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
ORDER BY c.relname
"""
COLUMNS = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
       pg_get_expr(d.adbin, d.adrelid), a.attidentity, a.attgenerated
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
"""
CONSTRAINTS = """
SELECT c.relname, con.conname, con.contype, pg_get_constraintdef(con.oid, true),
       con.condeferrable, con.condeferred
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
ORDER BY c.relname, con.conname
"""
INDEXES = """
SELECT t.relname, i.relname, pg_get_indexdef(ix.indexrelid), ix.indisunique, ix.indisprimary,
       EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid = ix.indexrelid)
FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public'
ORDER BY t.relname, i.relname
"""
TRIGGERS = """
SELECT c.relname, tg.tgname, pg_get_triggerdef(tg.oid)
FROM pg_trigger tg JOIN pg_class c ON c.oid = tg.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND NOT tg.tgisinternal
ORDER BY 1, 2
"""
FUNCTIONS = """
SELECT p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')'
FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
ORDER BY 1
"""
EXTENSIONS = "SELECT extname FROM pg_extension ORDER BY 1"
SEQUENCES = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S' ORDER BY 1
"""
MIGRATIONS = "SELECT app, name FROM django_migrations ORDER BY app, name"


def _strip_names(definition: str, table: str) -> str:
    """A name-independent signature for an index definition."""

    definition = re.sub(r"INDEX \S+ ON", "INDEX ON", definition)
    return definition.replace(f"public.{table}", table)


def snapshot(dsn: str) -> dict[str, object]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(TABLES)
        tables: dict[str, dict[str, object]] = {
            name: {"columns": {}, "constraints": {}, "indexes": {}, "triggers": {}}
            for (name,) in cur.fetchall()
        }
        cur.execute(COLUMNS)
        for table, column, data_type, not_null, default, identity, generated in cur.fetchall():
            tables[table]["columns"][column] = {
                "type": data_type,
                "not_null": not_null,
                "default": default,
                "identity": identity or None,
                "generated": generated or None,
            }
        cur.execute(CONSTRAINTS)
        for table, name, kind, definition, deferrable, deferred in cur.fetchall():
            tables[table]["constraints"][name] = {
                "kind": {"p": "primary", "f": "foreign", "u": "unique", "c": "check", "x": "exclusion"}.get(kind, kind),
                "definition": definition,
                "deferrable": deferrable,
                "deferred": deferred,
            }
        cur.execute(INDEXES)
        for table, name, definition, unique, primary, backs_constraint in cur.fetchall():
            tables[table]["indexes"][name] = {
                "definition": definition,
                "signature": _strip_names(definition, table),
                "unique": unique,
                "primary": primary,
                "backs_constraint": backs_constraint,
            }
        cur.execute(TRIGGERS)
        for table, name, definition in cur.fetchall():
            tables[table]["triggers"][name] = definition
        cur.execute(FUNCTIONS)
        functions = [row[0] for row in cur.fetchall()]
        cur.execute(EXTENSIONS)
        extensions = [row[0] for row in cur.fetchall()]
        cur.execute(SEQUENCES)
        sequences = [row[0] for row in cur.fetchall()]
        cur.execute(MIGRATIONS)
        migrations = [f"{app}.{name}" for app, name in cur.fetchall()]
    return {
        "tables": tables,
        "functions": functions,
        "extensions": extensions,
        "sequences": sequences,
        "migrations": migrations,
    }


def _by_signature(items: dict[str, dict[str, object]], key: str) -> dict[str, str]:
    return {str(value[key]): name for name, value in items.items()}


def compare(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    """Differences from A (historical) to B (canonical)."""

    ta, tb = a["tables"], b["tables"]
    report: dict[str, object] = {
        "tables_only_in_a": sorted(set(ta) - set(tb)),
        "tables_only_in_b": sorted(set(tb) - set(ta)),
        "columns": [],
        "constraints": [],
        "indexes": [],
        "triggers": [],
        "functions": {"only_in_a": sorted(set(a["functions"]) - set(b["functions"])),
                      "only_in_b": sorted(set(b["functions"]) - set(a["functions"]))},
        "extensions": {"only_in_a": sorted(set(a["extensions"]) - set(b["extensions"])),
                       "only_in_b": sorted(set(b["extensions"]) - set(a["extensions"]))},
        "sequences": {"only_in_a": sorted(set(a["sequences"]) - set(b["sequences"])),
                      "only_in_b": sorted(set(b["sequences"]) - set(a["sequences"]))},
        "shared_tables": len(set(ta) & set(tb)),
    }
    for table in sorted(set(ta) & set(tb)):
        ca, cb = ta[table]["columns"], tb[table]["columns"]
        for column in sorted(set(ca) | set(cb)):
            if ca.get(column) != cb.get(column):
                report["columns"].append({"table": table, "column": column,
                                          "a": ca.get(column), "b": cb.get(column)})
        for kind, signature_key in (("constraints", "definition"), ("indexes", "signature")):
            xa, xb = ta[table][kind], tb[table][kind]
            sig_a, sig_b = _by_signature(xa, signature_key), _by_signature(xb, signature_key)
            for signature in sorted(set(sig_a) | set(sig_b)):
                name_a, name_b = sig_a.get(signature), sig_b.get(signature)
                if name_a and name_b:
                    if name_a != name_b:
                        report[kind].append({"table": table, "change": "renamed",
                                             "a": name_a, "b": name_b, "definition": signature})
                    elif xa[name_a] != xb[name_b]:
                        report[kind].append({"table": table, "change": "attributes",
                                             "name": name_a, "a": xa[name_a], "b": xb[name_b]})
                else:
                    report[kind].append({"table": table,
                                         "change": "only_in_a" if name_a else "only_in_b",
                                         "name": name_a or name_b, "definition": signature})
        if ta[table]["triggers"] != tb[table]["triggers"]:
            report["triggers"].append({"table": table, "a": ta[table]["triggers"],
                                       "b": tb[table]["triggers"]})
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--dsn", required=True)
    snap.add_argument("--out", required=True)
    cmp = sub.add_parser("compare")
    cmp.add_argument("a")
    cmp.add_argument("b")
    cmp.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        data = snapshot(args.dsn)
        Path(args.out).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
        print(f"{len(data['tables'])} tables, {len(data['migrations'])} applied migrations")
        return 0
    result = compare(json.loads(Path(args.a).read_text()), json.loads(Path(args.b).read_text()))
    text = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    summary = {key: (len(value) if isinstance(value, list) else value)
               for key, value in result.items()}
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
