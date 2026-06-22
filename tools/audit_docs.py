import os
import re
import sys
from pathlib import Path

# Set ROOT_DIR to current working directory
ROOT_DIR = Path(os.getcwd()).resolve()
sys.path.append(str(ROOT_DIR))

# Import FastAPI app to inspect routes
from server.app.main import app  # noqa: E402


def get_registered_routes():
    routes = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            path = route.path
            for method in route.methods:
                routes[(method, path)] = route
    return routes


def audit_markdown_file(file_path: Path, registered_routes):  # noqa: PLR0912
    content = ""
    for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            with open(file_path, encoding=encoding) as f:
                content = f.read()
            break
        except Exception:  # noqa: S112
            continue

    if not content:
        return ["Could not decode file with any encoding."]

    # Strip code blocks to avoid false positives on examples
    content_stripped = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content_stripped = re.sub(r"`[^`\n]+`", "", content_stripped)

    errors = []

    # 1. Audit API Endpoints mentioned in markdown
    api_pattern = re.compile(
        r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+" r"(/api/v1/[a-zA-Z0-9_\-\/\{\}\?\=\&]+)"
    )
    for match in api_pattern.finditer(content_stripped):
        method, path = match.groups()
        clean_path = path.split("?")[0].rstrip("/")

        found = False
        for r_method, r_path in registered_routes.keys():
            if r_method == method:
                # Convert path to regex
                pattern_str = "^" + re.sub(r"\{[a-zA-Z0-9_]+\}", "[^/]+", r_path).rstrip("/") + "$"
                if re.match(pattern_str, clean_path):
                    found = True
                    break

        if not found:
            exact_match_keys = [
                k
                for k in registered_routes.keys()
                if k[0] == method and k[1].rstrip("/") == clean_path
            ]
            if not exact_match_keys:
                errors.append(
                    f"Outdated/Invalid API Endpoint: {method} {path} (Normalized: {clean_path})"
                )

    # 2. Audit file links
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for match in link_pattern.finditer(content_stripped):
        text, link = match.groups()
        if link.startswith(("http://", "https://", "mailto:", "#")):
            continue

        if link.startswith("file:///"):
            link_path_str = link.replace("file:///", "")
            # If on Windows, replace leading drive letter slash if needed
            if len(link_path_str) > 2 and link_path_str[1] == ":":  # noqa: PLR2004
                link_path = Path(link_path_str)
            else:
                link_path = Path("/" + link_path_str)
        else:
            clean_link = link.split("#")[0]
            if not clean_link:
                continue
            link_path = (file_path.parent / clean_link).resolve()

        if not link_path.exists():
            # Special check: see if the link refers to a different path
            errors.append(f"Broken File Link: '{link}' (Resolved to: {link_path})")

    return errors


def main():
    out_lines = []
    out_lines.append("Fetching registered routes from FastAPI app...")
    registered_routes = get_registered_routes()
    out_lines.append(f"Found {len(registered_routes)} registered route-method pairs.")

    docs_dir = ROOT_DIR / "docs"
    out_lines.append(f"Scanning documentation in: {docs_dir}")

    total_files = 0
    total_errors = 0

    for root, _dirs, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                file_path = Path(root) / file
                total_files += 1
                errors = audit_markdown_file(file_path, registered_routes)
                if errors:
                    out_lines.append(f"\n[ERROR] In file: {file_path.relative_to(ROOT_DIR)}")
                    for err in errors:
                        out_lines.append(f"  - {err}")
                        total_errors += 1

    msg = f"\nAudit complete. Scanned {total_files} files. Found {total_errors} errors/warnings."
    out_lines.append(msg)

    report_content = "\n".join(out_lines)
    print(report_content)

    with open(ROOT_DIR / "audit_results_utf8.txt", "w", encoding="utf-8") as f:
        f.write(report_content)


if __name__ == "__main__":
    main()
