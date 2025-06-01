import boto3, uuid, logging
import numpy as np
from PIL import Image
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
    filename = str(uuid.uuid4()) + allowed_mime_types[file.content_type]
    try:
        s3.upload_fileobj(file.file, settings.bucket_name, filename)
    except:
        raise HTTPException(status_code=500, detail="File could not be uploaded")
    return filename

def get_file(filename: str):
    s3_res = boto3.resource('s3', endpoint_url=settings.minio_endpoint)
    bucket = s3_res.Bucket(settings.bucket_name)
    obj = bucket.Object(filename)
    response = obj.get()
    file_stream = response['Body']
    im = Image.open(file_stream).convert("RGB")
    return np.array(im)