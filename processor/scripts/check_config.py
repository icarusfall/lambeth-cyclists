import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from config.settings import get_settings, validate_settings

try:
    validate_settings()
    print("✓ Configuration validated successfully!")
except Exception as e:
    print(f"✗ Configuration error: {e}")

