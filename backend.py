import boto3
import json
import os
from ec2_metadata import ec2_metadata
from face_recognition import face_match
import time
import logging

REGION = "us-east-1"
REQUEST_QUEUE = ""
RESPONSE_QUEUE = ""
INPUT_BUCKET = ""
OUTPUT_BUCKET = ""
IMG_DIR = "img_dir"
os.makedirs(IMG_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sqs_client = boto3.client('sqs', region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)
ec2_client = boto3.client('ec2', region_name=REGION)

def get_message():
    sqs_response = sqs_client.receive_message(QueueUrl=REQUEST_QUEUE, MaxNumberOfMessages=1, WaitTimeSeconds=5)
    if "Messages" not in sqs_response:
        return None, None
    msg = sqs_response['Messages'][0]
    logging.info(f"message received: {msg['Body']} [id: {msg['MessageId']}]")
    return msg['ReceiptHandle'], msg['Body']

def send_response(req_id, file_name, result):
    name, _ = os.path.splitext(file_name)
    sqs_client.send_message(QueueUrl=RESPONSE_QUEUE, MessageBody=json.dumps({'request_id':req_id, 'result': f'{name}:{result}'}))

def delete_message(id):
    sqs_client.delete_message(QueueUrl=REQUEST_QUEUE, ReceiptHandle=id)
    logging.info(f"message deleted")

def download_image(file_name):
    download_path = os.path.join(IMG_DIR, file_name)
    s3_client.download_file(INPUT_BUCKET, file_name, download_path)
    logging.info(f"{file_name} downloaded successfully")
    return download_path

def upload_result(file_name, result):
    key, _ = os.path.splitext(file_name)
    s3_response = s3_client.put_object(Bucket=OUTPUT_BUCKET, Key=key, Body=result)
    logging.info(f'{file_name}:{result} uploaded successfully [tag: {s3_response['ETag']}]')

def stop_instance():
    logging.info(f'stopping {ec2_metadata.instance_id}')
    ec2_client.stop_instances(InstanceIds=[ec2_metadata.instance_id])

if __name__ == "__main__":
    logging.info("backend application started")
    while True:
        try:
            msg_id, request = get_message()
            # stop instance 
            if(msg_id is None):
                logging.info("no messages in queue")
                stop_instance()
                break
            request_json = json.loads(request)
            file_name = request_json['file_name']
            req_id = request_json['request_id']
            # process request
            img_path = download_image(file_name)
            result = face_match(img_path, 'data.pt')[0]
            upload_result(file_name, result)
            send_response(req_id, file_name, result)
            # clean up
            delete_message(msg_id)
            os.remove(img_path)
        except KeyboardInterrupt:
            logging.info("backend application stopped")
            break
        except Exception as e:
            logging.info(f"Error: {e}", stack_info=True)
            time.sleep(0.5)
