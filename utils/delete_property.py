import os
from pathlib import Path

def delete_property_image(image_url: str):
    """Deletes the local image file associated with a property."""
    if not image_url:
        return
    
    try:
        file_path = Path(image_url)
        # pathlib safely removes the file if it exists
        if file_path.exists():
            file_path.unlink(missing_ok=True)
            print(f"🗑️ Deleted property image file: {image_url}")
    except Exception as e:
        print(f"⚠️ Failed to delete image file {image_url}: {e}")