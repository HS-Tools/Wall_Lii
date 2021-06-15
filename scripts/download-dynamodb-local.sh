#!/bin/bash

set -e

curl --output dynamodb_local_latest.zip  https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.zip
unzip dynamodb_local_latest.zip -d dynamodb-local
rm dynamodb_local_latest.zip

