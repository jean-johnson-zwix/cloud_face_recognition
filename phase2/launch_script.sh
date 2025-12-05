#!/bin/bash

AMI_ID="ami-027709079d46d363c" 
INSTANCE_TYPE="t3.micro"
KEY_NAME="web-instance-key-pair"
IAM_ROLE_NAME="CSE546_AppTier_IAMRole" 
SECURITY_GROUP_ID="sg-036aec1bae8f1cac4"
SUBNET_ID="subnet-004b9f27e00047b64" 

echo "Starting to launch 15 instances..."
# Loop from 1 to 15
for i in $(seq 1 15)
do
    INSTANCE_NAME="app-tier-instance-$i"

    echo "---"
    echo "Launching $INSTANCE_NAME..."

    # This command launches one instance and gets its ID
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id $AMI_ID \
        --instance-type $INSTANCE_TYPE \
        --key-name "$KEY_NAME" \
        --iam-instance-profile Name="$IAM_ROLE_NAME" \
        --security-group-ids $SECURITY_GROUP_ID \
        --subnet-id $SUBNET_ID \
        --count 1 \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --query "Instances[0].InstanceId" \
        --output text)

    if [ $? -ne 0 ]; then
        echo "!! FAILED to launch $INSTANCE_NAME. Stopping script."
        exit 1
    fi

    echo "Launched $INSTANCE_NAME with ID: $INSTANCE_ID"

    # This is the "launch stopped" requirement.
    # We wait for it to be "running" so we can then stop it.
    echo "Waiting for $INSTANCE_ID to be running..."
    aws ec2 wait instance-running --instance-ids $INSTANCE_ID

    echo "Stopping $INSTANCE_ID..."
    aws ec2 stop-instances --instance-ids $INSTANCE_ID

    echo "Done with $INSTANCE_NAME."
done

echo "---"
echo "All 15 instances have been launched and stopped."