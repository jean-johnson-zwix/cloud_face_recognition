import boto3
import csv

client = boto3.client('sdb',
                      aws_access_key_id='',
                      aws_secret_access_key='',
                      region_name='us-east-1')

# create domain
domain_name = '1232752380-simpleDB'
create_response = client.create_domain(
    DomainName=domain_name
)
print(f'create domain response: {create_response}')

# populate data

with open('data.csv', mode='r', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    print(f"Starting upload to SimpleDB domain '{domain_name}'...")
    for row in reader:
        attributes = [
            {"Name": 'Result', 'Value':row['Results'], 'Replace':True}
        ]
        print(f"  -> Processing item: {row['Image']}")
        client.put_attributes(
            DomainName=domain_name,
            ItemName=row['Image'],
            Attributes=attributes
        )