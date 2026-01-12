import logging, random
def lambda_handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    print("INFO: health check ok")
    if random.random() < 0.4:
        print("ERROR: simulated failure: TimeoutError connecting to DB")
    return {"ok": True}