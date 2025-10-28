from flask import Flask, request
import os
import boto3
import threading
import uuid
import logging
import json
import time

app = Flask(__name__)

REGION = "us-east-1"
REQUEST_QUEUE = ""
RESPONSE_QUEUE = ""
AWS_BUCKET_NAME=""
AWS_SIMPLEDB_DOMAIN_NAME=""

sqs_client = boto3.client('sqs', region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

result_cache = {}
cache_lock = threading.Lock()

def listen():
    while True:
        try:
            # poll for messages
            response = sqs_client.receive_message(QueueUrl=RESPONSE_QUEUE, MaxNumberOfMessages=10, WaitTimeSeconds=5)
            if "Messages" not in response:
                continue
            read_messages = []
            # store all messages in cache
            for message in response['Messages']:
                message_body = json.loads(message['Body'])
                req_id = message_body.get('request_id')
                result = message_body.get('result')
                with cache_lock:
                    result_cache[req_id] = result
                logging.info(f"result received for {req_id} -> {result}")
                read_messages.append({'Id': message['MessageId'], 'ReceiptHandle':message['ReceiptHandle']})
            # delete all read messages
            if read_messages:
                sqs_client.delete_message_batch(QueueUrl=RESPONSE_QUEUE, Entries=read_messages)
        except Exception as e:
            logging.info(f"Error when polling responses: {e}")

def send_request(req_id, file_name):
    message = json.dumps({'request_id': req_id, 'file_name': file_name})
    sqs_client.send_message(QueueUrl=REQUEST_QUEUE, MessageBody=message)
    logging.info(f'request sent for {req_id} -> {message}')

def upload_file(inputFile, file_name):
    s3_client.put_object(Body=inputFile, Bucket=AWS_BUCKET_NAME, Key=file_name)

@app.route('/', methods=['POST'])
def handle_request():

    # get file
    if 'inputFile' not in request.files:
        return "missing_file", 400
    inputFile = request.files['inputFile']
    if inputFile.filename == '':
        return "missing_file",400
    file_name = inputFile.filename

    # upload to s3
    upload_file(inputFile, file_name)

    # send request to app tier request queue
    req_id = str(uuid.uuid4())
    send_request(req_id, file_name)

    # poll local cache for 50s
    start_time = time.time()
    while time.time() - start_time < 50:
        result = None
        with cache_lock:
            result = result_cache.pop(req_id, None)
        if result:
            logging.info(f'response retrieved for {req_id} -> {result}')
            return result,200
        time.sleep(0.05)
    return "request_timeout",500

logging.info('Starting Queue Listener...')
queue_listener = threading.Thread(target=listen, daemon=True)
queue_listener.start()

if __name__== '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)