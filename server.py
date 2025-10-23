from flask import Flask, request
import os
import boto3
app = Flask(__name__)

AWS_BUCKET_NAME="1232752380-in-bucket"
AWS_SIMPLEDB_DOMAIN_NAME="1232752380-simpleDB"
s3_client = boto3.client('s3', region_name='us-east-1')
sdb_client = boto3.client('sdb', region_name='us-east-1')
@app.route('/', methods=['POST'])
def handle_request():

    # get file
    if 'inputFile' not in request.files:
        return "missing_file", 400
    inputFile = request.files['inputFile']
    if inputFile.filename == '':
        return "missing_file",400
    file_name = os.path.splitext(inputFile.filename)[0]

    # store in s3
    s3_client.put_object(Body=inputFile, Bucket=AWS_BUCKET_NAME, Key=inputFile.filename)

    # fetch recognition result
    sdb_response = sdb_client.get_attributes(
        DomainName=AWS_SIMPLEDB_DOMAIN_NAME,
        ItemName=file_name,
        ConsistentRead=False
    )
    if 'Attributes' not in sdb_response:
        return "file_not_found", 404
    recognition = next(item['Value'] for item in sdb_response['Attributes'] if item['Name'] == 'Result')
    return f"{file_name}:{recognition}"

if __name__== '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)