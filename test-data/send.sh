#! /bin/bash

URL=$1
DATA=$2

curl --data-binary "payload=`cat $DATA`" $URL
