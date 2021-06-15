#!/bin/bash

folder="$1"

pushd "$folders"

java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb -inMemory

popd