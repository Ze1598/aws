import json, os, string, random, re, time
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get("TABLE_NAME", "UrlShortener")
table = dynamodb.Table(TABLE_NAME)

SAFE = string.ascii_letters + string.digits
CODE_LEN = 6
URL_RE = re.compile(r'^https?://', re.I)
MAX_URL_LEN = 2048  # basic sanity limit

def _make_code(length=CODE_LEN):
    return ''.join(random.choices(SAFE, k=length))

def _put_unique_mapping(long_url, retries=5):
    """Unique shortCode via conditional writes; retry on collision."""
    code = _make_code()
    for _ in range(retries):
        try:
            table.put_item(
                Item={
                    "shortCode": code,
                    "longUrl": long_url,
                    "clicks": 0,
                    "createdAt": int(time.time()),
                    "lastAccessed": 0
                },
                ConditionExpression="attribute_not_exists(shortCode)"
            )
            return code
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                code = _make_code()
            else:
                raise
    raise RuntimeError("Could not generate unique code")

def lambda_handler(event, context):
    try:
        # Parse JSON body safely
        body_raw = event.get("body")
        if not body_raw:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing body"})}
        try:
            body = json.loads(body_raw) if isinstance(body_raw, str) else body_raw
        except json.JSONDecodeError:
            return {"statusCode": 400, "body": json.dumps({"error": "Body must be valid JSON"})}

        long_url = (body or {}).get("url", "").strip()
        if not long_url or not URL_RE.match(long_url):
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid or missing 'url' (must start with http(s)://)"})}
        if len(long_url) > MAX_URL_LEN:
            return {"statusCode": 400, "body": json.dumps({"error": "URL too long"})}

        code = _put_unique_mapping(long_url)

        # Build base URL from API Gateway request context (works in real invocations)
        rc = event.get("requestContext") or {}
        domain = rc.get("domainName")
        stage  = rc.get("stage")
        base_url = f"https://{domain}/{stage}" if domain and stage else "https://your-api-url"

        resp = {"shortUrl": f"{base_url}/{code}", "code": code}
        print(json.dumps({"event":"shorten_success","code":code,"len":len(long_url)}))
        return {"statusCode": 200, "headers": {"Content-Type":"application/json"}, "body": json.dumps(resp)}

    except Exception as e:
        print(json.dumps({"event":"shorten_error","error":str(e)}))
        return {"statusCode": 500, "body": json.dumps({"error": "Internal error"})}

