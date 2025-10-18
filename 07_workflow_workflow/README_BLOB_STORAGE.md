# Workflow Workflow - Azure Blob Storage Image Upload

This workflow demonstrates how to upload images to Azure Blob Storage with publicly accessible URIs using the Agent Framework.

## Features

- ✅ Automatic image detection and processing
- ✅ Upload images to Azure Blob Storage
- ✅ Generate publicly accessible URLs
- ✅ Automatic container creation with public blob access
- ✅ Image analysis using OpenAI
- ✅ Unique blob naming with timestamps
- ✅ Content type detection

## Setup

### 1. Azure Storage Account

First, you need an Azure Storage Account. If you don't have one:

```bash
# Login to Azure
az login

# Create a resource group (if needed)
az group create --name my-resource-group --location eastus

# Create a storage account
az storage account create \
  --name mystorageaccount \
  --resource-group my-resource-group \
  --location eastus \
  --sku Standard_LRS
```

### 2. Get Connection String

Get your storage account connection string:

```bash
az storage account show-connection-string \
  --name mystorageaccount \
  --resource-group my-resource-group \
  --output tsv
```

### 3. Configure Environment

Copy the example environment file and add your connection string:

```bash
cp .env.example .env
```

Edit `.env` and replace `YOUR_ACCOUNT_NAME` and `YOUR_ACCOUNT_KEY` with your actual values, or paste the entire connection string from the previous step.

### 4. Install Dependencies

```bash
pip install azure-storage-blob azure-identity agent-framework
```

## Usage

### Running the Workflow

```bash
python workflow.py
```

This will start the DevUI server at http://localhost:8090

### Testing Image Upload

1. Place an image file in the directory (e.g., `test_image_01.png`)
2. In the DevUI, submit a workflow request with the image path
3. The workflow will:
   - Detect it's an image
   - Upload it to Azure Blob Storage
   - Return a publicly accessible URL
   - Analyze the image using OpenAI

### Example Request

```json
{
  "path": "test_image_01.png"
}
```

## Workflow Steps

When an image is detected, the workflow follows this path:

1. **InputPreprocessor** - Validates the file exists and is an image
2. **BlobStorageUploader** - Uploads to Azure Blob Storage and returns public URL
3. **ImageAnalyzer** - Analyzes the image using the public blob URL
4. **SpamDetector** - Checks for spam indicators
5. **MessageResponder** or **SpamHandler** - Processes based on spam detection
6. **FinalProcessor** - Completes the workflow

## BlobStorageUploader Configuration

The `BlobStorageUploader` executor accepts the following parameters:

```python
blob_uploader = BlobStorageUploader(
    id="blob_uploader",
    connection_string="<optional-connection-string>",  # Defaults to env var
    container_name="images"  # Default container name
)
```

### Container Access

The container is created with **Public Blob** access, meaning:
- ✅ Anyone with the blob URL can read the blob
- ❌ Container listing is not publicly accessible
- ❌ Write operations require authentication

To change this behavior, modify the `public_access` parameter in the `BlobStorageUploader.handle_email_content()` method.

## BlobUploadResult

The uploader returns a `BlobUploadResult` with:

- `blob_url`: Publicly accessible URL
- `blob_name`: Unique blob name with timestamp
- `container_name`: Container where blob is stored
- `content_type`: MIME type of the uploaded file
- `upload_timestamp`: ISO format timestamp
- `file_size_bytes`: Size of the uploaded file
- `original_path`: Original file path

## Security Considerations

⚠️ **Important Security Notes:**

1. **Connection String**: Never commit your `.env` file with real credentials
2. **Public Access**: Blobs are publicly readable - don't upload sensitive images
3. **Container Names**: Use meaningful names that reflect access level
4. **Blob Naming**: Current implementation uses timestamps - consider adding user IDs for multi-tenant scenarios

## Customization

### Change Container Access Level

Edit the `BlobStorageUploader` class:

```python
# Private container (no public access)
public_access=None

# Container-level public read access
public_access=PublicAccess.Container
```

### Custom Blob Naming

Modify the blob name generation in `handle_email_content()`:

```python
# Current: timestamp_filename.ext
blob_name = f"{timestamp}_{input_path.name}"

# Alternative: Add user ID or other metadata
blob_name = f"user_{user_id}/{timestamp}_{input_path.name}"
```

### Add Metadata

```python
blob_client.upload_blob(
    data,
    overwrite=True,
    content_settings={"content_type": content_type},
    metadata={
        "uploaded_by": "workflow",
        "original_name": input_path.name,
        "timestamp": timestamp
    }
)
```

## Troubleshooting

### Connection Error

```
ValueError: Azure Storage connection string not provided
```

**Solution**: Set the `AZURE_STORAGE_CONNECTION_STRING` environment variable or pass it directly to the executor.

### Upload Failed

```
azure.core.exceptions.ResourceNotFoundError
```

**Solution**: Verify your storage account name and key are correct in the connection string.

### Blob Not Publicly Accessible

**Solution**: Ensure the container was created with `public_access=PublicAccess.Blob`. You can verify in Azure Portal under Container → Properties.

## Example Output

```
Successfully uploaded test_image_01.png to https://mystorageaccount.blob.core.windows.net/images/20251018_143022_test_image_01.png
Image analysis complete for 20251018_143022_test_image_01.png
```

## Learn More

- [Azure Blob Storage Documentation](https://docs.microsoft.com/azure/storage/blobs/)
- [Agent Framework Documentation](https://aka.ms/agent-framework)
- [Azure Storage Python SDK](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/storage/azure-storage-blob)
