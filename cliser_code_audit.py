from pathlib import Path
import ast
import re

ROOT = Path.cwd()

EXCLUDE = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
}

PY_DIRS = [
    "api",
    "node",
    "cli",
    "scripts",
    "tests",
]

print("=" * 100)
print("CLISER DATA NODE — CODEBASE REVIEW")
print("=" * 100)
print(f"ROOT: {ROOT}")
print()

# ============================================================
# 01 — INVENTÁRIO
# ============================================================

python_files = []

for directory in PY_DIRS:
    base = ROOT / directory

    if not base.exists():
        continue

    for path in base.rglob("*.py"):
        if any(part in EXCLUDE for part in path.parts):
            continue

        python_files.append(path)

python_files.sort()

print("[01] PYTHON FILES")
print(f"Total: {len(python_files)}")
print()

# ============================================================
# 02 — SINTAXE
# ============================================================

syntax_errors = []

for path in python_files:
    try:
        compile(
            path.read_text(),
            str(path),
            "exec",
        )
    except SyntaxError as exc:
        syntax_errors.append(
            (
                str(path),
                exc.lineno,
                exc.msg,
            )
        )
    except Exception:
        pass

print("[02] SYNTAX")
print(f"Syntax errors: {len(syntax_errors)}")

for filename, line, message in syntax_errors:
    print(
        f"  ERROR {filename}:{line}: {message}"
    )

print()

# ============================================================
# 03 — IMPORTS
# ============================================================

imports = []

for path in python_files:
    try:
        tree = ast.parse(path.read_text())
    except Exception:
        continue

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    (
                        str(path),
                        alias.name,
                    )
                )

        elif isinstance(node, ast.ImportFrom):
            imports.append(
                (
                    str(path),
                    node.module or "",
                )
            )

print("[03] IMPORT MAP")
print(f"Import statements: {len(imports)}")
print()

# ============================================================
# 04 — CONFIGURAÇÃO
# ============================================================

print("[04] CONFIGURATION SCAN")

config_files = [
    "api/config.py",
    "api/rate_limit.py",
    "api/rate_limit_policy.py",
    "api/rate_limit_middleware.py",
    "node/config.py",
]

for filename in config_files:

    path = ROOT / filename

    if not path.exists():
        print(f"  MISSING: {filename}")
        continue

    print(f"  OK: {filename}")

    text = path.read_text()

    patterns = [
        r"MAX_[A-Z0-9_]+",
        r"MIN_[A-Z0-9_]+",
        r"DEFAULT_[A-Z0-9_]+",
        r"LIMIT_[A-Z0-9_]+",
        r"QUOTA_[A-Z0-9_]+",
        r"RATE_[A-Z0-9_]+",
    ]

    values = set()

    for pattern in patterns:
        values.update(
            re.findall(
                pattern,
                text,
            )
        )

    for value in sorted(values):
        print(f"    {value}")

print()

# ============================================================
# 05 — CONFIGURAÇÕES IMPORTANTES
# ============================================================

print("[05] GLOBAL CONFIGURATION REFERENCES")

tokens = [
    "MAX_OBJECT_SIZE_BYTES",
    "MAX_UPLOAD_SIZE_BYTES",
    "RATE_LIMIT",
    "QUOTA",
    "OBJECT_TOO_LARGE",
    "UPLOAD_TOO_LARGE",
    "DELETED",
    "ACTIVE",
    "PREPARED",
    "COMMITTED",
    "ROLLBACK",
    "FAILED",
    "PENDING",
    "AUTH_REQUIRED",
    "AUTH_INVALID",
    "AUTH_REVOKED",
    "NAMESPACE_NOT_FOUND",
    "NAMESPACE_ACCESS_DENIED",
]

for token in tokens:

    matches = []

    for path in python_files:

        try:
            text = path.read_text()
        except Exception:
            continue

        count = text.count(token)

        if count:
            matches.append(
                (
                    str(path),
                    count,
                )
            )

    total = sum(
        count
        for _, count in matches
    )

    print(
        f"\n  {token}: {total} occurrence(s)"
    )

    for filename, count in matches[:15]:
        print(
            f"    {filename}: {count}"
        )

print()

# ============================================================
# 06 — EXCEÇÕES
# ============================================================

print("[06] EXCEPTION CLASSES")

exceptions = []

for path in python_files:

    try:
        tree = ast.parse(
            path.read_text()
        )
    except Exception:
        continue

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        if not (
            "Error" in node.name
            or "Exception" in node.name
        ):
            continue

        bases = []

        for base in node.bases:

            if isinstance(
                base,
                ast.Name,
            ):
                bases.append(
                    base.id
                )

            elif isinstance(
                base,
                ast.Attribute,
            ):
                bases.append(
                    base.attr
                )

        exceptions.append(
            (
                str(path),
                node.name,
                ",".join(bases),
            )
        )

for filename, name, base in exceptions:
    print(
        f"  {filename} :: "
        f"{name}({base})"
    )

print()

# ============================================================
# 07 — ROTAS
# ============================================================

print("[07] API ROUTES")

route_pattern = re.compile(
    r'@(router|app)\.'
    r'(get|post|put|patch|delete|head)\('
)

routes = []

for path in (
    ROOT / "api"
).rglob("*.py"):

    try:
        lines = path.read_text().splitlines()
    except Exception:
        continue

    for number, line in enumerate(
        lines,
        1,
    ):

        if route_pattern.search(line):

            routes.append(
                (
                    str(path),
                    number,
                    line.strip(),
                )
            )

print(
    f"Routes detected: {len(routes)}"
)

for filename, number, line in routes:
    print(
        f"  {filename}:{number}: {line}"
    )

print()

# ============================================================
# 08 — PERMISSÕES
# ============================================================

print(
    "[08] AUTHORIZATION / "
    "PERMISSION REFERENCES"
)

permission_tokens = [
    "object.create",
    "object.read",
    "object.delete",
    "namespace.manage",
    "namespace.read",
    "node.manage",
    "quota.manage",
]

for token in permission_tokens:

    matches = []

    for path in python_files:

        text = path.read_text(
            errors="ignore"
        )

        if token in text:
            matches.append(
                str(path)
            )

    print(
        f"  {token}: "
        f"{len(matches)} file(s)"
    )

    for filename in matches:
        print(
            f"    {filename}"
        )

print()

# ============================================================
# 09 — BANCO
# ============================================================

print("[09] DATABASE TABLE REFERENCES")

tables = [
    "api_credentials",
    "blocks",
    "manifest_blocks",
    "manifests",
    "namespaces",
    "objects",
    "quotas",
    "transaction_journal",
    "transactions",
]

for table in tables:

    count = 0
    files = []

    for path in python_files:

        text = path.read_text(
            errors="ignore"
        )

        if table in text:

            count += text.count(
                table
            )

            files.append(
                str(path)
            )

    print(
        f"  {table}: "
        f"{count} reference(s) / "
        f"{len(files)} file(s)"
    )

print()

# ============================================================
# 10 — ESTADOS
# ============================================================

print("[10] OBJECT / TRANSACTION STATE MODEL")

states = [
    "ACTIVE",
    "DELETED",
    "PENDING",
    "FAILED",
    "PREPARED",
    "COMMITTED",
    "ROLLBACK",
]

for state in states:

    locations = []

    for path in python_files:

        text = path.read_text(
            errors="ignore"
        )

        if state in text:
            locations.append(
                str(path)
            )

    print(
        f"  {state}: "
        f"{len(locations)} file(s)"
    )

print()

# ============================================================
# 11 — HTTP
# ============================================================

print("[11] HTTP STATUS CODE SCAN")

status_codes = {}

for path in python_files:

    text = path.read_text(
        errors="ignore"
    )

    for match in re.finditer(
        r"status_code\s*=\s*(\d{3})",
        text,
    ):

        code = match.group(1)

        status_codes.setdefault(
            code,
            set(),
        ).add(
            str(path)
        )

for code in sorted(status_codes):

    print(
        f"  {code}: "
        f"{len(status_codes[code])} file(s)"
    )

print()

# ============================================================
# 12 — TODO
# ============================================================

print("[12] TODO / FIXME / HACK")

markers = []

for path in python_files:

    try:
        lines = path.read_text().splitlines()
    except Exception:
        continue

    for number, line in enumerate(
        lines,
        1,
    ):

        if re.search(
            r"\b(TODO|FIXME|HACK|XXX)\b",
            line,
        ):

            markers.append(
                (
                    str(path),
                    number,
                    line.strip(),
                )
            )

print(
    f"Markers: {len(markers)}"
)

for filename, number, line in markers:
    print(
        f"  {filename}:{number}: {line}"
    )

print()

# ============================================================
# 13 — MÓDULOS GRANDES
# ============================================================

print("[13] LARGE MODULES")

sizes = []

for path in python_files:

    try:
        lines = len(
            path.read_text().splitlines()
        )
    except Exception:
        continue

    sizes.append(
        (
            lines,
            str(path),
        )
    )

for lines, filename in sorted(
    sizes,
    reverse=True,
)[:20]:

    print(
        f"  {lines:5} lines  "
        f"{filename}"
    )

print()

# ============================================================
# 14 — TESTES
# ============================================================

print("[14] TEST INVENTORY")

test_files = list(
    (ROOT / "tests").rglob(
        "test_*.py"
    )
)

print(
    f"Test files: {len(test_files)}"
)

total_tests = 0

for path in sorted(test_files):

    try:
        text = path.read_text()

        count = len(
            re.findall(
                r"^\s*(async\s+)?def\s+test_",
                text,
                re.MULTILINE,
            )
        )

    except Exception:
        count = 0

    total_tests += count

    print(
        f"  {count:3} tests  {path}"
    )

print(
    f"Total discovered tests: "
    f"{total_tests}"
)

print()

# ============================================================
# 15 — BACKUPS / TEMP
# ============================================================

print("[15] BACKUP / TEMP FILES")

patterns = [
    "*.bak",
    "*.backup",
    "*.old",
    "*.orig",
    "*.pre_*",
    "*~",
]

found = set()

for pattern in patterns:

    for path in ROOT.rglob(pattern):

        if any(
            part in EXCLUDE
            for part in path.parts
        ):
            continue

        found.add(
            str(path)
        )

for filename in sorted(found):
    print(
        f"  {filename}"
    )

print()

# ============================================================
# 16 — ARQUIVOS DE CONFIGURAÇÃO
# ============================================================

print("[16] CONFIG / DOCUMENTATION FILES")

for pattern in [
    "*.json",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.ini",
    "*.env",
    "*.md",
]:

    matches = []

    for path in ROOT.rglob(pattern):

        if any(
            part in EXCLUDE
            for part in path.parts
        ):
            continue

        matches.append(
            str(path)
        )

    if matches:

        print(
            f"\n  {pattern}: "
            f"{len(matches)}"
        )

        for filename in sorted(
            matches
        )[:30]:
            print(
                f"    {filename}"
            )

print()

# ============================================================
# SUMMARY
# ============================================================

summary = {
    "python_files": len(
        python_files
    ),
    "syntax_errors": len(
        syntax_errors
    ),
    "routes": len(routes),
    "exceptions": len(exceptions),
    "test_files": len(test_files),
    "tests": total_tests,
    "todo_markers": len(markers),
    "backup_temp_files": len(found),
}

print("=" * 100)
print("AUDIT SUMMARY")
print("=" * 100)

for key, value in summary.items():

    print(
        f"{key:25}: {value}"
    )

print()
print(
    "AUDIT ONLY — "
    "nenhum arquivo de projeto foi alterado."
)
print("=" * 100)
