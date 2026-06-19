"""
Comprehensive system verification script.

Checks all components of the SwipePads News Scraper:
database, images, exports, configuration, and modules.
"""

import sys
import importlib
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.database import init_db, get_article_count, get_all_articles, get_articles_without_summary


def check(label: str, condition: bool, detail: str = "") -> bool:
    """Print a check result and return pass/fail."""
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return condition


def verify_all(full: bool = False):
    """Run all verification checks."""
    print("=" * 60)
    print("SwipePads Scraper — System Verification")
    print("=" * 60)
    print()

    results = []
    db_path = str(Config.DATABASE_FULL_PATH)

    # 1. Configuration
    print("[Configuration]")
    results.append(check("Config loads", True))
    results.append(check("User agent set", bool(Config.USER_AGENT), Config.USER_AGENT))
    results.append(check("Database path set", bool(Config.DATABASE_PATH), str(Config.DATABASE_FULL_PATH)))

    has_api_key = Config.ANTHROPIC_API_KEY and 'your_' not in Config.ANTHROPIC_API_KEY.lower()
    results.append(check("Anthropic API key", has_api_key,
                         "configured" if has_api_key else "NOT SET — summarization won't work"))
    results.append(check("Claude model", bool(Config.CLAUDE_MODEL), Config.CLAUDE_MODEL))
    print()

    # 2. Modules
    print("[Modules]")
    modules = ['src.config', 'src.database', 'src.scraper', 'src.parser',
               'src.image_downloader', 'src.summarizer', 'src.pipeline',
               'src.exporter', 'src.cleanup', 'src.scheduler']
    for mod in modules:
        try:
            importlib.import_module(mod)
            results.append(check(f"Import {mod}", True))
        except Exception as e:
            results.append(check(f"Import {mod}", False, str(e)))
    print()

    # 3. Database
    print("[Database]")
    db_exists = Path(db_path).exists()
    results.append(check("Database file exists", db_exists, db_path))

    if db_exists:
        try:
            init_db(db_path)
            count = get_article_count(db_path)
            results.append(check("Database readable", True, f"{count} articles"))

            articles = get_all_articles(db_path=db_path)
            with_summary = sum(1 for a in articles if a.get('summary'))
            with_image = sum(1 for a in articles if a.get('image_path'))
            results.append(check("Articles with summaries", True, f"{with_summary}/{count}"))
            results.append(check("Articles with images", True, f"{with_image}/{count}"))

            unsummarized = get_articles_without_summary(db_path=db_path)
            results.append(check("Unsummarized articles", True, f"{len(unsummarized)} pending"))

            db_size = Path(db_path).stat().st_size
            results.append(check("Database size", True, f"{db_size / 1024:.1f} KB"))
        except Exception as e:
            results.append(check("Database readable", False, str(e)))
    print()

    # 4. Images
    print("[Images]")
    images_dir = Path('images')
    if images_dir.exists():
        image_files = list(images_dir.rglob('*'))
        image_files = [f for f in image_files if f.is_file()]
        total_size = sum(f.stat().st_size for f in image_files)
        results.append(check("Images directory", True,
                            f"{len(image_files)} files ({total_size / (1024*1024):.1f} MB)"))
    else:
        results.append(check("Images directory", True, "no images yet"))
    print()

    # 5. Exports
    print("[Exports]")
    exports_dir = Path('exports')
    if exports_dir.exists():
        export_files = list(exports_dir.glob('*'))
        results.append(check("Exports directory", True, f"{len(export_files)} files"))
    else:
        results.append(check("Exports directory", True, "no exports yet"))
    print()

    # 6. Logs
    print("[Logs]")
    log_file = Config.LOG_FILE_FULL_PATH
    if log_file.exists():
        log_size = log_file.stat().st_size
        results.append(check("Log file", True, f"{log_size / 1024:.1f} KB"))
    else:
        results.append(check("Log file", True, "not created yet"))

    pid_file = Path('scheduler.pid')
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        results.append(check("Scheduler PID", True, f"PID {pid}"))
    else:
        results.append(check("Scheduler", True, "not running"))
    print()

    # 7. Tests (if --full)
    if full:
        print("[Tests]")
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short'],
            capture_output=True, text=True
        )
        passed = result.returncode == 0
        # Count tests from output
        for line in result.stdout.split('\n'):
            if 'passed' in line:
                results.append(check("Pytest", passed, line.strip()))
                break
        else:
            results.append(check("Pytest", passed, result.stderr.strip()[:100] if not passed else "OK"))
        print()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r)
    failed = total - passed

    print("=" * 60)
    if failed == 0:
        print(f"ALL {total} CHECKS PASSED")
    else:
        print(f"{passed}/{total} PASSED — {failed} FAILED")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verify SwipePads Scraper system')
    parser.add_argument('--full', action='store_true', help='Run full verification including tests')
    args = parser.parse_args()

    sys.exit(verify_all(full=args.full))
