#!/bin/bash

# This is all boilerplate. It will need to be modified to work with the current environment.
# $BUCKET $REGION should be GitHub repo secrets. $NAME can be discovered by env variable.

mkdir dist
cp src/* dist/

pip3 install -r requirements.txt -t dist/
aws cloudformation package --template-file template.yaml --s3-bucket $BUCKET --s3-prefix $NAME --output-template processed.template.yaml --region $REGION
aws cloudformation deploy --template-file processed.template.yaml --stack-name $NAME --capabilities CAPABILITY_IAM --region $REGION

rm processed.template.yaml
rm -rf dist/

