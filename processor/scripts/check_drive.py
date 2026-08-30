import _bootstrap  # noqa: F401  (repo-root imports + UTF-8 console)

from services.storage_service import StorageService

storage = StorageService()
storage.authenticate()
print("✓ Google Drive authentication successful!")

# Verify folder access
if storage.verify_folder_access():
    print("✓ Drive folder accessible!")
    folder_info = storage.get_folder_info()
    print(f"  Folder: {folder_info['name']}")
    print(f"  URL: {folder_info['url']}")
else:
    print("✗ Cannot access Drive folder")