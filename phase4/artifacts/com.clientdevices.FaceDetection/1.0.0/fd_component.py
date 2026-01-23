import os
import time
import json
import boto3
import base64
import requests
import numpy as np
import logging
from facenet_pytorch import MTCNN
from PIL import Image, ImageDraw, ImageFont
import traceback
from io import BytesIO
import awsiot.greengrasscoreipc
from awsiot.greengrasscoreipc.clientv2 import GreengrassCoreIPCClientV2
from awsiot.greengrasscoreipc.model import (QOS, IoTCoreMessage)

# CONGIGURATIONS
ASU_ID = ""
ACCOUNT_ID = ""
MQTT_TOPIC = f"clients/{ASU_ID}-IoTThing"
REQUEST_QUEUE_URL = f"https://sqs.us-east-1.amazonaws.com/{ACCOUNT_ID}/{ASU_ID}-req-queue"
RESPONSE_QUEUE_URL = f"https://sqs.us-east-1.amazonaws.com/{ACCOUNT_ID}/{ASU_ID}-resp-queue"

# Logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Model Config
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection
# Queue Config
sqs = boto3.client('sqs')
# Greengrass Config
greengrass_core = GreengrassCoreIPCClientV2()

def on_stream_event(event):
    try:
        # Step 0: Read MQTT message & parse request
        mqtt_message = str(event.message.payload, "utf-8")
        topic = event.message.topic_name
        message_payload = json.loads(mqtt_message)
        encoded_img = message_payload.get("encoded")
        request_id = message_payload.get("request_id")
        filename = message_payload.get("filename")
        decoded_img = base64.b64decode(encoded_img)
        logger.info(f'Got file: {filename} with request_id: {request_id} on {topic}')

        # Step-1: Read the image
        img = Image.open(BytesIO(decoded_img)).convert("RGB")
        img = np.array(img)
        img = Image.fromarray(img)

        # Step:2 Face detection
        face, prob = mtcnn(img, return_prob=True, save_path=None)
        if face is None:
            # Response Message
            message = {
                'result': "No-Face",
                'request_id': request_id
            }
            sqs.send_message(QueueUrl=RESPONSE_QUEUE_URL, MessageBody=json.dumps(message))
            logger.info(f'{request_id} -> no face')
            return
        face_img = face - face.min()  # Shift min value to 0
        face_img = face_img / face_img.max()  # Normalize to range [0,1]
        face_img = (face_img * 255).byte().permute(1, 2, 0).numpy()  # Convert to uint8
        # Convert numpy array to PIL Image
        face_pil = Image.fromarray(face_img, mode="RGB")

        # Step: 3 Send request into queue
        # Encode the image
        buffered = BytesIO()
        face_pil.save(buffered, format="JPEG")
        encoded_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
        # Request Message
        message = {
            'face_image': encoded_img,
            'request_id': request_id
        }
        sqs.send_message(QueueUrl=REQUEST_QUEUE_URL, MessageBody=json.dumps(message))
        logger.info(f'{request_id} -> request submitted')
    
    except Exception as e:
        print(f"An error occured: {e}")
        traceback.print_exc()

def on_stream_error(error):
    logger.error(f"An error occured: {error}")

def on_stream_closed():
    logger.error("The stream has closed")

if __name__ == "__main__":
    
    # Subscribe to the MQTT TOPIC
    subscription = greengrass_core.subscribe_to_iot_core(
            topic_name=MQTT_TOPIC, qos=QOS.AT_LEAST_ONCE,
            on_stream_event=on_stream_event, on_stream_error=on_stream_error, on_stream_closed=on_stream_closed
        )
    logger.info(f"Subscribed to topic: {MQTT_TOPIC}")
    
    while True:
        time.sleep(10)