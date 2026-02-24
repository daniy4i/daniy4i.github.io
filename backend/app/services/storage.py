import io
import boto3
from app.core.config import settings


s3 = boto3.client(
    "s3",
    endpoint_url=settings.s3_endpoint_url,
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_secret_key,
)


def ensure_bucket() -> None:
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if settings.s3_bucket not in buckets:
        s3.create_bucket(Bucket=settings.s3_bucket)


def upload_bytes(key: str, payload: bytes, content_type: str = "application/octet-stream"):
    ensure_bucket()
    s3.upload_fileobj(
        io.BytesIO(payload),
        settings.s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def download_file(key: str, path: str):
    ensure_bucket()
    s3.download_file(settings.s3_bucket, key, path)


def signed_url(key: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=3600,
    )
