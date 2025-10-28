import boto3
import time
import logging

REGION = "us-east-1"
REQUEST_QUEUE = ""
MAX_POOL_SIZE = 15
CONTROLLER_DELAY_SECONDS=10

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

sqs_client = boto3.client('sqs', region_name=REGION)
ec2_client = boto3.client('ec2', region_name=REGION)

def get_pending_request_count():
    response = sqs_client.get_queue_attributes(QueueUrl=REQUEST_QUEUE, AttributeNames=['ApproximateNumberOfMessages'])
    count = int(response['Attributes']['ApproximateNumberOfMessages'])
    logging.info(f'pending requests in queue: {count}')
    return count

def get_available_instances():
    # get stopped app tier instances
    instance_list = []
    response_pages = ec2_client.get_paginator('describe_instances').paginate(
        Filters = [{'Name':'instance-state-name', 'Values': ['stopped']}, {'Name':'tag:Name', 'Values': ['app-tier-instance-*']}]
    )
    for response in response_pages:
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_list.append(instance['InstanceId'])
    logging.info(f'available {len(instance_list)} instances: {instance_list}')
    return instance_list

def start_instances(instance_list):
    ec2_client.start_instances(InstanceIds=instance_list)
    logging.info(f'started {len(instance_list)} instance(s): {instance_list}')

if __name__ == "__main__":
    logging.info("controller script has started")
    while True:
        try:
            request_count = get_pending_request_count()
            if request_count >= 1:
                available_instances = get_available_instances()
                if request_count <= len(available_instances):
                    start_instances(available_instances[:request_count])
                else:
                    start_instances(available_instances)
            # Add delay
            time.sleep(CONTROLLER_DELAY_SECONDS)
        except KeyboardInterrupt:
            logging.info("controller script has stopped")
            break
        except Exception as e:
            logging.info(f"Error: {e}")