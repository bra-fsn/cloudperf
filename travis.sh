#!/bin/sh

cloudperf write-prices --s3-bucket cloudperf-data --file /tmp/prices.json.gz --no-update
cloudperf write-combined --s3-bucket cloudperf-data --file /tmp/combined.json.gz
