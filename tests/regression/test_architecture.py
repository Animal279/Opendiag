"""Guard the declared import boundaries against actual application source."""

import ast
from importlib.util import resolve_name
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAYERS = {"domain", "ports", "core", "adapters", "application", "ui", "security"}
ALLOWED_INTERNAL = {
    "domain": {"domain"},
    "ports": {"ports", "domain"},
    "core": {"core", "domain"},
    "adapters": {"adapters", "ports", "domain", "core"},
    "application": {"application", "ports", "domain", "adapters"},
    "ui": {"ui", "ports", "application"},
    "security": {"security"},
}
COMPOSITION_ROOTS = {
    "src/application/app_container.py",
    "src/application/protocol_bootstrapper.py",
}
QT_ALLOWED = {"core", "adapters", "ui"}
STARTUP_MODULES = {"main.py", "src/__init__.py", "src/version.py", "src/app_setup.py"}
APP_STARTUP_MODULES = {"main.py", "src/app_setup.py"}


def string_literal(node: ast.AST | None, package: str) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id == "__package__":
        return package
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = string_literal(node.left, package)
        right = string_literal(node.right, package)
        if left is not None and right is not None:
            return left + right
    return None


def source_imports(tree: ast.AST, package: str):
    """Resolve relative imports and recognized importlib/builtin aliases."""
    importlib_aliases = {"importlib"}
    builtin_aliases = {"builtins"}
    importer_aliases = {"__import__"}
    import_module_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, None
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
                if alias.name == "builtins":
                    builtin_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                try:
                    module = resolve_name("." * node.level + (node.module or ""), package)
                except (ImportError, ValueError) as error:
                    yield node.lineno, None, f"invalid relative import: {error}"
                    continue
            else:
                module = node.module or ""
            yield node.lineno, module, None
            # from src import core and from .. import adapters must not hide a layer.
            if module == "src":
                for alias in node.names:
                    if alias.name == "*":
                        yield node.lineno, None, "wildcard root import hides the imported layer"
                    else:
                        yield node.lineno, f"{module}.{alias.name}", None
            if module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_aliases.add(alias.asname or alias.name)
            if module == "builtins":
                for alias in node.names:
                    if alias.name == "__import__":
                        importer_aliases.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_import_module = (
            isinstance(function, ast.Name) and function.id in import_module_aliases
        ) or (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id in importlib_aliases
            and function.attr == "import_module"
        )
        is_builtin_import = (
            isinstance(function, ast.Name) and function.id in importer_aliases
        ) or (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id in builtin_aliases
            and function.attr == "__import__"
        )
        if not (is_import_module or is_builtin_import):
            continue
        target = string_literal(node.args[0] if node.args else None, package)
        if target is None:
            yield node.lineno, None, "dynamic import target needs an auditable import policy"
            continue
        if is_import_module and target.startswith("."):
            package_node = node.args[1] if len(node.args) > 1 else None
            for keyword in node.keywords:
                if keyword.arg == "package":
                    package_node = keyword.value
            target_package = string_literal(package_node, package)
            if target_package is None:
                yield node.lineno, None, "relative dynamic import needs a known package"
                continue
            try:
                target = resolve_name(target, target_package)
            except (ImportError, ValueError) as error:
                yield node.lineno, None, f"invalid dynamic import: {error}"
                continue
        if is_builtin_import:
            level_node = node.args[4] if len(node.args) > 4 else None
            for keyword in node.keywords:
                if keyword.arg == "level":
                    level_node = keyword.value
            if level_node is not None:
                if not isinstance(level_node, ast.Constant) or type(level_node.value) is not int:
                    yield node.lineno, None, "dynamic import level must be a literal integer"
                    continue
                if level_node.value:
                    try:
                        target = resolve_name("." * level_node.value + target, package)
                    except (ImportError, ValueError) as error:
                        yield node.lineno, None, f"invalid dynamic import: {error}"
                        continue
            if target == "src":
                fromlist_node = node.args[3] if len(node.args) > 3 else None
                for keyword in node.keywords:
                    if keyword.arg == "fromlist":
                        fromlist_node = keyword.value
                if fromlist_node is not None:
                    if not isinstance(fromlist_node, (ast.Tuple, ast.List)):
                        yield node.lineno, None, "root dynamic import needs a literal fromlist"
                    else:
                        for item in fromlist_node.elts:
                            name = string_literal(item, package)
                            if name is None or name == "*":
                                yield node.lineno, None, "root dynamic import hides the imported layer"
                            else:
                                yield node.lineno, f"src.{name}", None
        yield node.lineno, target, None


def test_application_imports_follow_layer_whitelist():
    failures = []
    sources = list((REPOSITORY_ROOT / "src").rglob("*.py"))
    entrypoint = REPOSITORY_ROOT / "main.py"
    if entrypoint.is_file():
        sources.append(entrypoint)
    for path in sorted(sources):
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        parts = path.relative_to(REPOSITORY_ROOT).with_suffix("").parts
        module_parts = parts[:-1] if parts[-1] == "__init__" else parts
        package_parts = module_parts if path.name == "__init__.py" else module_parts[:-1]
        package = ".".join(package_parts)
        layer = parts[1] if len(parts) > 2 else None
        is_composition_root = relative in COMPOSITION_ROOTS
        if layer is None:
            if relative not in STARTUP_MODULES:
                failures.append(f"{relative}: top-level code must be initialization or version metadata")
        elif layer not in LAYERS:
            failures.append(f"{relative}: unrecognized business layer {layer}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for line, target, issue in source_imports(tree, package):
            location = f"{relative}:{line}"
            if issue:
                failures.append(f"{location}: {issue}")
                continue
            assert target is not None
            imported_parts = target.split(".")
            root = imported_parts[0]
            if root in {"PyQt5", "PyQt6", "PySide2"}:
                failures.append(f"{location}: GUI binding {root} is forbidden")
            elif root == "src":
                if len(imported_parts) < 2 or imported_parts[1] == "version":
                    continue
                imported_layer = imported_parts[1]
                if relative in APP_STARTUP_MODULES:
                    allowed = LAYERS | {"app_setup"}
                elif layer is None:
                    allowed = set()
                else:
                    allowed = ALLOWED_INTERNAL[layer]
                if is_composition_root:
                    allowed = allowed | {"core", "ui"}
                if imported_layer not in allowed:
                    failures.append(f"{location}: {layer} must not import {target}")
            elif root == "PySide6":
                if layer not in QT_ALLOWED and not is_composition_root and relative not in APP_STARTUP_MODULES:
                    failures.append(f"{location}: {layer} must not depend on Qt")
            elif root not in sys.stdlib_module_names and layer != "adapters":
                failures.append(f"{location}: external dependency {target} is not allowed in {layer}")
    assert not failures, "\n" + "\n".join(failures)
