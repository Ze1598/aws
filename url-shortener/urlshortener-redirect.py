import json, os, time
import boto3

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get("TABLE_NAME", "UrlShortener")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    try:
        path_params = event.get("pathParameters") or {}
        code = (path_params.get("shortCode") or "").strip()
        if not code:
            return {"statusCode": 400, "body": "Bad Request: missing shortCode"}

        resp = table.get_item(Key={"shortCode": code})
        item = resp.get("Item")
        if not item:
            return {"statusCode": 404, "body": "Not Found"}

        long_url = item["longUrl"]

        # Best-effort analytics update (non-blocking for redirect)
        try:
            table.update_item(
                Key={"shortCode": code},
                UpdateExpression="SET clicks = if_not_exists(clicks, :z) + :one, lastAccessed = :now",
                ExpressionAttributeValues={":z": 0, ":one": 1, ":now": int(time.time())}
            )
        except Exception:
            pass

        print(json.dumps({"event":"redirect","code":code}))
        return {"statusCode": 302, "headers": {"Location": long_url}}

    except Exception as e:
        print(json.dumps({"event":"redirect_error","error":str(e)}))
        return {"statusCode": 500, "body": json.dumps({"error":"Internal error"})}

