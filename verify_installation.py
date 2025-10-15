#!/usr/bin/env python3
"""Verify need_scanner installation and dependencies."""

import sys
from pathlib import Path


def check_python_version():
    """Check Python version is 3.10+."""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  ✗ Python 3.10+ required")
        return False
    print("  ✓ Python version OK")
    return True


def check_dependencies():
    """Check all required dependencies."""
    required = [
        "openai",
        "pydantic",
        "pydantic_settings",
        "dotenv",
        "typer",
        "loguru",
        "numpy",
        "pandas",
        "sklearn",
        "rapidfuzz",
        "requests",
    ]

    optional = {
        "faiss": "FAISS indexing (optional)",
        "streamlit": "Dashboard (optional)"
    }

    print("\nChecking required dependencies...")
    all_ok = True

    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            all_ok = False

    print("\nChecking optional dependencies...")
    for package, description in optional.items():
        try:
            __import__(package)
            print(f"  ✓ {package} - {description}")
        except ImportError:
            print(f"  ○ {package} - Not installed ({description})")

    return all_ok


def check_project_structure():
    """Check project files exist."""
    print("\nChecking project structure...")

    required_files = [
        "src/need_scanner/__init__.py",
        "src/need_scanner/cli.py",
        "src/need_scanner/config.py",
        "src/need_scanner/schemas.py",
        "src/need_scanner/utils.py",
        "src/need_scanner/fetchers/reddit.py",
        "src/need_scanner/processing/clean.py",
        "src/need_scanner/processing/dedupe.py",
        "src/need_scanner/processing/embed.py",
        "src/need_scanner/processing/cluster.py",
        "src/need_scanner/analysis/summarize.py",
        "src/need_scanner/analysis/scoring.py",
        "src/need_scanner/export/writer.py",
        "tests/mock_posts.json",
        "tests/test_json_parsing.py",
        ".env.example",
        "requirements.txt",
        "README.md",
    ]

    all_ok = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            all_ok = False

    return all_ok


def check_env_file():
    """Check .env file exists."""
    print("\nChecking configuration...")

    if Path(".env").exists():
        print("  ✓ .env file exists")

        # Check for API key
        with open(".env", "r") as f:
            content = f.read()
            if "OPENAI_API_KEY=sk-" in content:
                print("  ✓ OPENAI_API_KEY appears to be set")
                return True
            elif "OPENAI_API_KEY=" in content:
                print("  ⚠ .env exists but OPENAI_API_KEY may not be set")
                print("    Please add your OpenAI API key to .env")
                return False
    else:
        print("  ✗ .env file not found")
        print("    Run: cp .env.example .env")
        print("    Then add your OPENAI_API_KEY")
        return False

    return True


def check_data_directory():
    """Check data directory setup."""
    print("\nChecking data directory...")

    data_dir = Path("data")
    raw_dir = Path("data/raw")

    if not data_dir.exists():
        data_dir.mkdir()
        print("  ✓ Created data/ directory")

    if not raw_dir.exists():
        raw_dir.mkdir()
        print("  ✓ Created data/raw/ directory")

    print("  ✓ Data directories ready")
    return True


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("need_scanner Installation Verification")
    print("=" * 60)

    checks = [
        ("Python Version", check_python_version()),
        ("Dependencies", check_dependencies()),
        ("Project Structure", check_project_structure()),
        ("Configuration", check_env_file()),
        ("Data Directory", check_data_directory()),
    ]

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✓ All checks passed! Installation is complete.")
        print("\nNext steps:")
        print("  1. Test JSON parsing: python tests/test_json_parsing.py")
        print("  2. Run with mock data: python -m need_scanner run --input tests/mock_posts.json --clusters 3")
        print("  3. Read QUICKSTART.md for usage examples")
        return 0
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Create .env file: cp .env.example .env")
        print("  - Add OPENAI_API_KEY to .env")
        return 1


if __name__ == "__main__":
    sys.exit(main())
