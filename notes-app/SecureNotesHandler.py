import os, json, time, uuid
import boto3, botocore
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
TABLE = dynamodb.Table(os.environ['TABLE_NAME'])

def _json(body, code=200):
    return {"statusCode": code,
            "headers": {"Content-Type": "application/json"},
            # First dump and load to enforce parsing as strings
            "body": json.dumps(json.loads(json.dumps(body, default=str)))}
            

def _uid(event):
    # API Gateway (REST) + Cognito User Pool Authorizer injects claims here:
    claims = (event.get("requestContext") or {}).get("authorizer", {}).get("claims", {})
    uid = claims.get("sub")
    if not uid:
        raise PermissionError("Missing user identity (JWT 'sub')")
    return uid

def lambda_handler(event, context):
    try:
        method = event.get("httpMethod")
        path   = event.get("resource") or event.get("path") or ""
        params = event.get("pathParameters") or {}
        uid = _uid(event)

        # POST /notes  -> create
        if method == "POST" and path.endswith("/notes"):
            body = json.loads(event.get("body") or "{}")
            text = (body.get("text") or "").strip()
            if not text:
                return _json({"error":"Missing 'text'"}, 400)
            now = int(time.time())
            note_id = str(uuid.uuid4())
            item = {"userId": uid, "noteId": note_id, "text": text,
                    "createdAt": now, "updatedAt": now}
            TABLE.put_item(Item=item)
            return _json(item, 201)

        # GET /notes  -> list current user's notes
        if method == "GET" and path.endswith("/notes") and not params.get("id"):
            resp = TABLE.query(KeyConditionExpression=Key("userId").eq(uid))
            return _json(resp.get("Items", []))

        # GET /notes/{id} -> retrieve one
        if method == "GET" and params.get("id"):
            nid = params["id"]
            resp = TABLE.get_item(Key={"userId": uid, "noteId": nid})
            item = resp.get("Item")
            if not item:
                return _json({"error":"Not Found"}, 404)
            return _json(item)

        # PUT /notes/{id} -> update text
        if method == "PUT" and params.get("id"):
            nid  = params["id"]
            body = json.loads(event.get("body") or "{}")
            text = (body.get("text") or "").strip()
            if not text:
                return _json({"error":"Missing 'text'"}, 400)
            now = int(time.time())
            try:
                resp = TABLE.update_item(
                    Key={"userId": uid, "noteId": nid},
                    UpdateExpression="SET #t=:t, updatedAt=:u",
                    ExpressionAttributeNames={"#t": "text"},
                    ExpressionAttributeValues={":t": text, ":u": now},
                    ConditionExpression="attribute_exists(noteId)",
                    ReturnValues="ALL_NEW"
                )
                return _json(resp["Attributes"])
            except botocore.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    return _json({"error":"Not Found"}, 404)
                raise

        # DELETE /notes/{id}
        if method == "DELETE" and params.get("id"):
            nid = params["id"]
            try:
                TABLE.delete_item(
                    Key={"userId": uid, "noteId": nid},
                    ConditionExpression="attribute_exists(noteId)"
                )
                return _json({"deleted": nid})
            except botocore.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    return _json({"error":"Not Found"}, 404)
                raise

        return _json({"error":"Route not found"}, 404)

    except PermissionError as e:
        return _json({"error": str(e)}, 401)
    except Exception as e:
        print(json.dumps({"event":"notes_error","err":str(e)}))
        return _json({"error":"Internal error"}, 500)

