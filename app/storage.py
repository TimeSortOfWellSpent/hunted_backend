import boto3, uuid, logging
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException

from app.config import settings

s3 = boto3.client("s3", endpoint_url=settings.minio_endpoint)
allowed_mime_types = {
    "image/jpeg": ".jpeg",
    "image/png": ".png",
}
def upload_file(file: UploadFile):
    if file.content_type not in allowed_mime_types.keys():
        raise HTTPException(status_code=400, detail="Forbidden file type")
    try:
        filename = str(uuid.uuid4()) + allowed_mime_types[file.content_type]
        s3.upload_fileobj(file.file, settings.bucket_name, filename)
    except ClientError as e:
        logging.error(e)
        return ''
    return filename