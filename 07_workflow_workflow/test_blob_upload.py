#!/usr/bin/env python3
"""
Simple test script for Azure Blob Storage upload functionality.
This script demonstrates uploading an image and getting a public URL.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
import mimetypes
from azure.storage.blob import BlobServiceClient, PublicAccess, ContentSettings
from azure.core.exceptions import ResourceExistsError


def upload_image_to_blob(
    file_path: str,
    connection_string: str | None = None,
    container_name: str = "images"
) -> dict:
    """
    Upload an image to Azure Blob Storage and return the public URL.
    
    Args:
        file_path: Path to the image file
        connection_string: Azure Storage connection string (uses env var if None)
        container_name: Name of the blob container
    
    Returns:
        Dictionary with upload details including the public blob URL
    """
    
    # Get connection string from parameter or environment
    conn_str = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    
    if not conn_str:
        raise ValueError(
            "Azure Storage connection string not provided. "
            "Set AZURE_STORAGE_CONNECTION_STRING environment variable or pass connection_string parameter."
        )
    
    # Validate file exists
    input_path = Path(file_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image file not found: {input_path}")
    
    # Create BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    
    # Get or create container with public access for blobs
    container_client = blob_service_client.get_container_client(container_name)
    
    # Check if container exists, create if it doesn't
    try:
        # Try to get container properties to check if it exists
        container_client.get_container_properties()
        print(f"✓ Using existing container '{container_name}'")
    except Exception as e:
        # Container doesn't exist, create it
        print(f"⏳ Creating container '{container_name}'...")
        try:
            container_client.create_container(public_access=PublicAccess.Blob)
            print(f"✓ Created container '{container_name}' with public blob access")
        except ResourceExistsError:
            # Race condition - container was created between check and create
            print(f"✓ Container '{container_name}' already exists")
        except Exception as create_error:
            print(f"❌ Failed to create container: {create_error}")
            raise
    
    # Generate unique blob name with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"{timestamp}_{input_path.name}"
    
    # Get content type
    content_type, _ = mimetypes.guess_type(str(input_path))
    if not content_type:
        content_type = "application/octet-stream"
    
    # Upload the file
    blob_client = container_client.get_blob_client(blob_name)
    
    file_size = input_path.stat().st_size
    
    print(f"⏳ Uploading {input_path.name} ({file_size:,} bytes)...")
    
    with open(input_path, "rb") as data:
        blob_client.upload_blob(
            data, 
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )
    
    # Get the public URL
    blob_url = blob_client.url
    
    result = {
        "blob_url": blob_url,
        "blob_name": blob_name,
        "container_name": container_name,
        "content_type": content_type,
        "upload_timestamp": datetime.now(timezone.utc).isoformat(),
        "file_size_bytes": file_size,
        "original_path": str(input_path),
    }
    
    print(f"✓ Successfully uploaded to Azure Blob Storage")
    print(f"  Public URL: {blob_url}")
    
    return result


def main():
    """Main function to test blob upload."""
    import sys
    
    # Check for file argument
    if len(sys.argv) < 2:
        print("Usage: python test_blob_upload.py <image_file_path>")
        print("\nExample:")
        print("  python test_blob_upload.py test_image_01.png")
        print("\nMake sure AZURE_STORAGE_CONNECTION_STRING is set in your environment.")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        result = upload_image_to_blob(file_path)
        
        print("\n" + "="*60)
        print("Upload Details:")
        print("="*60)
        for key, value in result.items():
            print(f"  {key}: {value}")
        print("="*60)
        
        print("\n✅ Test completed successfully!")
        print(f"🌐 Your image is now publicly accessible at:")
        print(f"   {result['blob_url']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
