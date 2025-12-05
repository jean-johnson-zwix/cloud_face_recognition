import os
import time
import json
import boto3
import torch
import base64
import numpy as np
from facenet_pytorch import MTCNN
from PIL import Image, ImageDraw, ImageFont
from facenet_pytorch import InceptionResnetV1
import traceback
from io import BytesIO

# Model Config
resnet = InceptionResnetV1(pretrained='vggface2').eval()
saved_data = torch.load('resnetV1_video_weights.pt')
embedding_list = saved_data[0]
name_list = saved_data[1]

# Queue Config
sqs = boto3.client('sqs')
RESPONSE_QUEUE_URL = os.environ['RESPONSE_QUEUE_URL']


def handler(event, context):

    for record in event['Records']:
        try:
            
            # Step 0: Parse request
            req = json.loads(record['body'])
            print(f"processing request: {req.get('request_id', 'unknown')}")
            decoded_img = base64.b64decode(req.get('face_image'))
            
            # Step 1: Load image as PIL
            face_pil = Image.open(BytesIO(decoded_img)).convert("RGB")
            # Step 2: Convert PIL to NumPy array (H, W, C) in range [0, 255]
            face_numpy = np.array(face_pil, dtype=np.float32)  # Convert to float for scaling
            # Step 3: Normalize values to [0,1] and transpose to (C, H, W)
            face_numpy /= 255.0  # Normalize to range [0,1]
            # Convert (H, W, C) → (C, H, W)
            face_numpy = np.transpose(face_numpy, (2, 0, 1))
            # Step 4: Convert NumPy to PyTorch tensor
            face_tensor = torch.tensor(face_numpy, dtype=torch.float32)
            if face_tensor is None:
                print('No face detected')
                continue
            emb = resnet(face_tensor.unsqueeze(0)).detach()  # detech is to make required gradient false
            dist_list  = []  # list of matched distances, minimum distance is used to identify the person
            for idx, emb_db in enumerate(embedding_list):
                dist = torch.dist(emb, emb_db).item()
                dist_list.append(dist)
            idx_min = dist_list.index(min(dist_list))
            result = name_list[idx_min]
           
            # Step 5: Send response to queue
            message = {
                "request_id": req.get('request_id'),
                "result": result
            }
            sqs.send_message(QueueUrl=RESPONSE_QUEUE_URL, MessageBody=json.dumps(message))
        
        except Exception as e:
            print(f"An error occured: {e}")
            traceback.print_exc()
    
    return {"statusCode": 200, "message": f"Processed {len(event['Records'])} record(s)"}
