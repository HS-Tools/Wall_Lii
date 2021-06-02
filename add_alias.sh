#!/bin/bash

Alias="$1"
PlayerNane="$2"

# arg checking
if [ -z "$Alias" ] ; then
    echo "Alias <$Alias> is not defined (arg 1)"
    exit -1
fi

# arg checking
if [ -z "$PlayerNane" ] ; then
    echo "PlayerNane <$PlayerNane> is not defined (arg 2)"
    exit -1
fi

## add item to table
aws dynamodb put-item \
  --table-name 'player-alias-table' \
  --item "{
    \"PlayerNane\": {\"S\": \"${PlayerNane}\"},
    \"Alias\": {\"S\": \"${Alias}\"},
  }"


## print out the updated table
aws dynamodb scan --table-name 'player-alias-table'


