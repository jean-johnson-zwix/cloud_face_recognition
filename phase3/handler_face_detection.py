import os
import json
import boto3
import base64
import requests
import numpy as np
from facenet_pytorch import MTCNN
from PIL import Image, ImageDraw, ImageFont
import traceback
from io import BytesIO

# Model Config
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20) # initializing mtcnn for face detection

# Queue Config
sqs = boto3.client('sqs')
REQUEST_QUEUE_URL = os.environ['REQUEST_QUEUE_URL']

def handler(event, context):

    try:
        # Step 0: Parse request
        req = json.loads(event.get('body'))
        decoded_img = base64.b64decode(req.get('content'))

        # Step-1: Read the image
        img = Image.open(BytesIO(decoded_img)).convert("RGB")
        img = np.array(img)
        img = Image.fromarray(img)

        # Step:2 Face detection
        face, prob = mtcnn(img, return_prob=True, save_path=None)
        if face is None:
            return {"statusCode":400, 'body':json.dumps({'error':'no face detected'})}
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
            'request_id': req.get('request_id')
        }
        sqs.send_message(QueueUrl=REQUEST_QUEUE_URL, MessageBody=json.dumps(message))
        return {"statusCode":200, 'body':json.dumps({'message':f"Request submitted successfully [req_id:{req.get('request_id')}]"})}
    
    except Exception as e:
        print(f"An error occured: {e}")
        traceback.print_exc()
        return {"statusCode":500, 'body':json.dumps({'error':'internal server error'})}
