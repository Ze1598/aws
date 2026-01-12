import os, json, base64, gzip, re, time, uuid
from io import BytesIO
import boto3

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
TABLE = dynamodb.Table(os.environ["TABLE_NAME"])
TOPIC_ARN = os.environ["TOPIC_ARN"]
LEVEL_RE = re.compile(os.environ.get("LEVEL_REGEX", r"(ERROR|Exception|Traceback|Timeout)"), re.I)

def _decode(event):
    # CloudWatch Logs → Lambda subscription payload
    data = event["awslogs"]["data"]
    raw = gzip.decompress(base64.b64decode(data))
    return json.loads(raw)  # {owner, logGroup, logStream, logEvents:[{id,timestamp,message}]}

def lambda_handler(event, context):
    decoded = _decode(event)
    group  = decoded["logGroup"]
    stream = decoded["logStream"]
    events = decoded.get("logEvents", [])

    matches = []
    for e in events:
        msg = e.get("message","")
        if LEVEL_RE.search(msg):
            matches.append({
                "service": group,
                "ts": int(e["timestamp"]),  # ms
                "level": "ERROR",
                "stream": stream,
                "id": e.get("id", str(uuid.uuid4())),
                "message": msg[:2000]  # keep bounded
            })

    # Write each match to DDB (simple, reliable, low volume)
    for m in matches:
        TABLE.put_item(Item=m)

    # Batch summary to SNS (no spam if no matches)
    if matches:
        sample = matches[0]["message"].strip().replace("\n"," ")[:180]
        summary = {
            "service": group,
            "count": len(matches),
            "example": sample,
            "stream": stream,
            "firstTs": matches[0]["ts"],
            "lastTs": matches[-1]["ts"]
        }
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=f"[ALERT] {group} matched {len(matches)} error log(s)",
            Message=json.dumps(summary, indent=2)
        )

    print(json.dumps({"event":"log_batch_done","group":group,"matched":len(matches)}))
    return {"statusCode": 200, "body": json.dumps({"ok": True, "matched": len(matches)})}
