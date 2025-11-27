import json, os, urllib.parse
import boto3, botocore

s3 = boto3.client('s3')
sns = boto3.client('sns')

BACKUP_BUCKET = os.environ['BACKUP_BUCKET']
TOPIC_ARN     = os.environ['TOPIC_ARN']

def _exists(bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
            return False
        raise

def lambda_handler(event, context):
    # S3 may send multiple records; process each safely & idempotently
    for rec in event.get('Records', []):
        if not rec.get('eventName','').startswith('ObjectCreated:'):
            # ignore non-create events (e.g., deletes)
            continue

        src_bucket = rec['s3']['bucket']['name']
        raw_key    = rec['s3']['object']['key']
        key        = urllib.parse.unquote_plus(raw_key)
        version_id = rec['s3']['object'].get('versionId')
        dest_key   = key   # mirror folder structure in backup bucket

        # Idempotency: if already copied, skip
        if _exists(BACKUP_BUCKET, dest_key):
            print(json.dumps({"event":"skip_copy","key":dest_key}))
            continue

        copy_source = {'Bucket': src_bucket, 'Key': key}
        if version_id:
            copy_source['VersionId'] = version_id

        # Server-side encrypt destination too
        s3.copy_object(
            Bucket=BACKUP_BUCKET,
            Key=dest_key,
            CopySource=copy_source,
            ServerSideEncryption='AES256'
        )

        msg = {
            "status": "COPIED",
            "sourceBucket": src_bucket,
            "sourceKey": key,
            "versionId": version_id,
            "backupBucket": BACKUP_BUCKET,
            "backupKey": dest_key
        }
        print(json.dumps({"event":"copied", **msg}))
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject="File Backed Up",
            Message=json.dumps(msg, indent=2)
        )

    return {"statusCode": 200, "body": json.dumps({"ok": True})}

