import ast
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

FILES = [
    "app/__init__.py",
    "app/calendar_tracker.py",
    "app/config.py",
    "app/db.py",
    "app/exporter.py",
    "app/fetcher.py",
    "app/main.py",
    "app/parser.py",
    "app/templates.py",
    "app/web.py",
    "scripts/harvest_all_history.py"
]

def check_files():
    base_dir = r"c:\Users\Admin\Desktop\project\POKETAN"
    has_error = False
    for rel_path in FILES:
        full_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(full_path):
            print(f"[MISSING] {rel_path}")
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                code = f.read()
            tree = ast.parse(code, filename=rel_path)
            print(f"[OK] {rel_path} parsed successfully.")
        except SyntaxError as e:
            print(f"[SYNTAX ERROR] {rel_path}: {e}")
            has_error = True
        except Exception as e:
            print(f"[ERROR] {rel_path}: {e}")
            has_error = True

    if not has_error:
        print("\nAll files compiled & AST parsed with zero syntax errors!")

if __name__ == "__main__":
    check_files()
