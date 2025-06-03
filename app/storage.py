import boto3, uuid, io
from PIL import Image
from botocore.config import Config
from fastapi import UploadFile, HTTPException
from botocore.exceptions import ClientError

from app.config import settings

s3_client = boto3.client(
    "s3",
    region_name='eu-central-1',
    config=Config(signature_version="s3v4")
)
rekognition_client = boto3.client(
    'rekognition',
    region_name='eu-central-1'
)
allowed_mime_types = {
    "image/jpeg": ".jpeg",
    "image/png": ".png",
}


def upload_file(file: UploadFile):
    if file.content_type not in allowed_mime_types.keys():
        raise HTTPException(status_code=400, detail="Forbidden file type")
    filename = str(uuid.uuid4()) + allowed_mime_types[file.content_type]
    s3_client.upload_fileobj(file.file, settings.bucket_name, filename)
    return filename


def generate_presigned_url(filename: str):
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object", Params={"Bucket": settings.bucket_name, "Key": filename}, ExpiresIn=3600
        )
    except ClientError:
        raise
    return url


def compare_faces(source: str, target: UploadFile) -> bool:
    img = Image.open(target.file)
    if img.mode != 'RGB':
        img = img.convert('RGB')

    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=75, optimize=True)
    photo_bytes = buffer.getvalue()
    response = rekognition_client.compare_faces(
        SourceImage={"S3Object": {"Bucket": settings.bucket_name, "Name": source}},
        TargetImage={"Bytes": photo_bytes},
        SimilarityThreshold=80
    )
    if len(response['FaceMatches']) == 0:
        return False
    return True
