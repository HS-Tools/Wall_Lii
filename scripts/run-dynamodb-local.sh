#!/bin/bash

folder="$1"

pushd "$folder"

java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -inMemory

popd