# cloudperf
## Measuring the relative performance of cloud resources

Cloudperf is a python helper for running benchmarks on cloud providers'
infrastructure (currently Amazon AWS/EC2 is supported) and getting/comparing
the results along with their price.

Features include:
* fetch and upload EC2 instance prices (both on-demand and spot) from/to S3
* run defined benchmarks on all EC2 node types in docker images
** ability to run more sophisticated benchmark setups (on one node), like launching a multi-instance distributed DB server and a benchmark client
** any docker image can be used for the benchmarks, the only requirement is to be able to produce a benchmark score
* CLI for updating/getting the gathered data

## Getting started

You can install the application with a simple `pip install cloudperf`.
Then you'll have the `cloudperf` executable, which is the main entry point to the
application.

### Cloudperf data

Cloudperf works with tabular data, stored in S3 (world readable published) in
compressed JSON files.
The three files are:
1. Prices: https://cloudperf-data.s3-us-west-2.amazonaws.com/prices.json.gz
1. Performance: https://cloudperf-data.s3-us-west-2.amazonaws.com/performance.json.gz
1. Combined: https://cloudperf-data.s3-us-west-2.amazonaws.com/combined.json.gz

Prices are constantly updated for many reasons:
1. new instance types come and old ones go
1. the prices can change
1. the spot prices change dynamically, very similarly to a stock exchange

The Performance data is updated in a much less frequent manner.
The Combined file is updated approximately daily and it's mainly for embedded
web, not for general use.

### Using the CLI

The CLI has two modes of operation:
1. get/show mode
1. update mode

The first is when you use the already compiled data, which contains the current
prices and benchmark results.
The second can be used to update either the price list or (re)run the benchmarks
and store the data. You can use this internally as well to run your own benchmarks.

The get mode has some common arguments:
* `--cols` for the columns you want to see. There are many columns in the data tables,
many of them are hidden by default, to make the output easier to read.
* `--sort` the column(s) to sort on
* `--filter` you can filter on the given column's data. You can use basic operators, like `>`, `<` and `=`

#### Getting the prices

If you execute `cloudperf prices`, it will fetch actual pricing data from S3 and
show it to you, like:
```
instanceType          region          spot-az  vcpu    memory     price
      t3.nano      eu-north-1      eu-north-1c     2     0.500   0.00160
      t3.nano       us-east-2       us-east-2c     2     0.500   0.00160
      t3.nano       us-east-1       us-east-1a     2     0.500   0.00160
      t3.nano       us-east-1       us-east-1f     2     0.500   0.00160
      t3.nano       us-east-1       us-east-1d     2     0.500   0.00160
      t3.nano       us-east-1       us-east-1c     2     0.500   0.00160
      t3.nano       us-east-1       us-east-1b     2     0.500   0.00160
      t3.nano      eu-north-1      eu-north-1a     2     0.500   0.00160
      t3.nano       us-west-2       us-west-2a     2     0.500   0.00160
      t3.nano       us-east-2       us-east-2b     2     0.500   0.00160
      t3.nano      eu-north-1      eu-north-1b     2     0.500   0.00160
      t3.nano       us-east-2       us-east-2a     2     0.500   0.00160
      t3.nano       eu-west-1       eu-west-1a     2     0.500   0.00170
      t3.nano       eu-west-1       eu-west-1c     2     0.500   0.00170
      t3.nano    ca-central-1    ca-central-1b     2     0.500   0.00170
      t3.nano      ap-south-1      ap-south-1b     2     0.500   0.00170
      t3.nano      ap-south-1      ap-south-1a     2     0.500   0.00170
      t3.nano       us-west-2       us-west-2c     2     0.500   0.00170
      t3.nano    ca-central-1    ca-central-1a     2     0.500   0.00170
      t3.nano       eu-west-1       eu-west-1b     2     0.500   0.00170
      t3.nano       eu-west-2       eu-west-2b     2     0.500   0.00180
      t3.nano    eu-central-1    eu-central-1c     2     0.500   0.00180
      t3.nano       us-west-2       us-west-2b     2     0.500   0.00180
      t3.nano       eu-west-2       eu-west-2a     2     0.500   0.00180
      t3.nano       eu-west-2       eu-west-2c     2     0.500   0.00180
      t3.nano    eu-central-1    eu-central-1a     2     0.500   0.00180
      t3.nano    eu-central-1    eu-central-1b     2     0.500   0.00180
      t3.nano       us-west-1       us-west-1b     2     0.500   0.00190
      t3.nano       us-west-1       us-west-1a     2     0.500   0.00190
      t3.nano  ap-northeast-1  ap-northeast-1a     2     0.500   0.00200
     t1.micro       eu-west-1       eu-west-1b     1     0.613   0.00200
      t3.nano  ap-southeast-2  ap-southeast-2b     2     0.500   0.00200
      t3.nano  ap-southeast-2  ap-southeast-2c     2     0.500   0.00200
      t3.nano  ap-southeast-2  ap-southeast-2a     2     0.500   0.00200
      t3.nano  ap-southeast-1  ap-southeast-1c     2     0.500   0.00200
     t1.micro       us-east-1       us-east-1b     1     0.613   0.00200
     t1.micro       us-east-1       us-east-1c     1     0.613   0.00200
```

You can filter for any columns, like for a given region:
```
cloudperf prices --filter region=us-west-2 | head -10
instanceType     region     spot-az  vcpu    memory    price
      t3.nano  us-west-2  us-west-2a     2     0.500   0.0016
      t3.nano  us-west-2  us-west-2c     2     0.500   0.0017
      t3.nano  us-west-2  us-west-2b     2     0.500   0.0018
     t1.micro  us-west-2  us-west-2a     1     0.613   0.0020
     t1.micro  us-west-2  us-west-2b     1     0.613   0.0020
     t1.micro  us-west-2  us-west-2c     1     0.613   0.0020
     t3.micro  us-west-2  us-west-2c     2     1.000   0.0031
     t3.micro  us-west-2  us-west-2a     2     1.000   0.0031
     t3.micro  us-west-2  us-west-2b     2     1.000   0.0031
```

https://bra-fsn.github.io/cloudperf/prices.html
