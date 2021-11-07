#!/bin/bash

ChannelName="$1"
PlayerNane="$2"

# arg checking
if [ -z "$ChannelName" ] ; then
    echo "ChannelName <$ChannelName> is not defined (arg 1)"
    exit -1
fi

# arg checking
if [ -z "$PlayerNane" ] ; then
    echo "PlayerNane <$PlayerNane> is not defined (arg 2)"
    exit -1
fi

## add item to table
aws dynamodb put-item \
  --table-name 'channel-table' \
  --item "{
    \"ChannelName\": {\"S\": \"${ChannelName}\"},
    \"PlayerNane\": {\"S\": \"${PlayerNane}\"},
  }"


## print out the updated table
aws dynamodb scan --table-name 'channel-table'


