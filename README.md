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
* `--filter` you can filter on the given column's data. You can use basic operators,
like `>`, `<`, `>=`, `<=` and `=`

#### Getting the prices

If you execute `cloudperf prices`, it will fetch actual pricing data from S3 and
show it to you, like:
```
$ cloudperf prices
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
$ cloudperf prices --filter region=us-west-2 | head -10
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

You can have multiple filters:
```
$ cloudperf prices --filter 'vcpu>=128' --filter region=us-west-2
instanceType     region     spot-az  vcpu  memory    price
 x1.32xlarge  us-west-2  us-west-2c   128  1952.0   4.0014
 x1.32xlarge  us-west-2  us-west-2b   128  1952.0   4.0014
 x1.32xlarge  us-west-2        None   128  1952.0  13.3380
 x1.32xlarge  us-west-2  us-west-2a   128  1952.0  13.3380
x1e.32xlarge  us-west-2        None   128  3904.0  26.6880
x1e.32xlarge  us-west-2  us-west-2b   128  3904.0  26.6880
x1e.32xlarge  us-west-2  us-west-2a   128  3904.0  26.6880
```

The spot-az column contains the Availability Zone (AZ) and the last known spot
price if available. spot-az None marks the on-demand price for the instance in
that region.

#### Getting the benchmark results
You can issue `cloudperf performance --no-combined` to get the latest benchmark
results. This will include all the benchmarks for the benchmarked instances and
their latest score.
By default, this will only show the benchmark results with the vCPU-numbered
concurrency (meaning the benchmark program ran with vCPU parallelism).
If you want to see benchmark results for each number of vCPUs, you can use for
example:
```
$ cloudperf performance --no-combined --no-maxcpu --filter instanceType=m5.24xlarge --filter benchmark_id=stress-ng:crc16
instanceType     benchmark_id  benchmark_cpus  benchmark_score
m5.24xlarge  stress-ng:crc16               1         153.4700
m5.24xlarge  stress-ng:crc16               2         305.4200
m5.24xlarge  stress-ng:crc16               3         457.2700
m5.24xlarge  stress-ng:crc16               4         607.5400
m5.24xlarge  stress-ng:crc16               5         750.4900
m5.24xlarge  stress-ng:crc16               6         897.9900
m5.24xlarge  stress-ng:crc16               7        1042.1200
m5.24xlarge  stress-ng:crc16               8        1186.4000
m5.24xlarge  stress-ng:crc16               9        1333.7000
m5.24xlarge  stress-ng:crc16              10        1480.6400
m5.24xlarge  stress-ng:crc16              11        1624.5700
m5.24xlarge  stress-ng:crc16              12        1773.9300
m5.24xlarge  stress-ng:crc16              13        1921.5400
m5.24xlarge  stress-ng:crc16              14        2066.2900
m5.24xlarge  stress-ng:crc16              15        2213.0600
m5.24xlarge  stress-ng:crc16              16        2359.9000
m5.24xlarge  stress-ng:crc16              17        2507.6800
m5.24xlarge  stress-ng:crc16              18        2653.8500
m5.24xlarge  stress-ng:crc16              19        2800.1600
m5.24xlarge  stress-ng:crc16              20        2945.6200
m5.24xlarge  stress-ng:crc16              21        3092.3500
m5.24xlarge  stress-ng:crc16              22        3238.4400
m5.24xlarge  stress-ng:crc16              23        3383.5900
m5.24xlarge  stress-ng:crc16              24        3528.6500
m5.24xlarge  stress-ng:crc16              25        3673.7700
m5.24xlarge  stress-ng:crc16              26        3821.0200
m5.24xlarge  stress-ng:crc16              27        3963.2900
m5.24xlarge  stress-ng:crc16              28        4109.5900
m5.24xlarge  stress-ng:crc16              29        4253.9200
m5.24xlarge  stress-ng:crc16              30        4400.6100
m5.24xlarge  stress-ng:crc16              31        4543.7900
m5.24xlarge  stress-ng:crc16              32        4690.0000
m5.24xlarge  stress-ng:crc16              33        4826.8500
m5.24xlarge  stress-ng:crc16              34        4938.4700
m5.24xlarge  stress-ng:crc16              35        5114.5600
m5.24xlarge  stress-ng:crc16              36        5256.2100
m5.24xlarge  stress-ng:crc16              37        5391.5700
m5.24xlarge  stress-ng:crc16              38        5532.8000
m5.24xlarge  stress-ng:crc16              39        5641.4900
m5.24xlarge  stress-ng:crc16              40        5797.2500
m5.24xlarge  stress-ng:crc16              41        5941.1000
m5.24xlarge  stress-ng:crc16              42        6072.0700
m5.24xlarge  stress-ng:crc16              45        6207.2000
m5.24xlarge  stress-ng:crc16              43        6208.1700
m5.24xlarge  stress-ng:crc16              44        6333.4600
m5.24xlarge  stress-ng:crc16              46        6508.2700
m5.24xlarge  stress-ng:crc16              47        6709.0500
m5.24xlarge  stress-ng:crc16              48        6869.4300
m5.24xlarge  stress-ng:crc16              50        6973.1700
m5.24xlarge  stress-ng:crc16              49        6973.2600
m5.24xlarge  stress-ng:crc16              51        7127.6400
m5.24xlarge  stress-ng:crc16              52        7327.4600
m5.24xlarge  stress-ng:crc16              53        7444.9100
m5.24xlarge  stress-ng:crc16              54        7546.5700
m5.24xlarge  stress-ng:crc16              55        7658.1300
m5.24xlarge  stress-ng:crc16              56        7708.0800
m5.24xlarge  stress-ng:crc16              57        7885.0400
m5.24xlarge  stress-ng:crc16              58        7994.7500
m5.24xlarge  stress-ng:crc16              59        8099.9600
m5.24xlarge  stress-ng:crc16              60        8211.5600
m5.24xlarge  stress-ng:crc16              61        8314.0200
m5.24xlarge  stress-ng:crc16              62        8434.1600
m5.24xlarge  stress-ng:crc16              63        8543.7900
m5.24xlarge  stress-ng:crc16              64        8650.0700
m5.24xlarge  stress-ng:crc16              65        8751.9500
m5.24xlarge  stress-ng:crc16              66        8861.1900
m5.24xlarge  stress-ng:crc16              67        8974.5600
m5.24xlarge  stress-ng:crc16              68        9083.7900
m5.24xlarge  stress-ng:crc16              69        9194.9700
m5.24xlarge  stress-ng:crc16              70        9305.0300
m5.24xlarge  stress-ng:crc16              71        9408.9300
m5.24xlarge  stress-ng:crc16              72        9504.9400
m5.24xlarge  stress-ng:crc16              73        9630.7000
m5.24xlarge  stress-ng:crc16              74        9739.4700
m5.24xlarge  stress-ng:crc16              75        9849.7800
m5.24xlarge  stress-ng:crc16              76        9955.6900
m5.24xlarge  stress-ng:crc16              77       10067.6800
m5.24xlarge  stress-ng:crc16              78       10163.1200
m5.24xlarge  stress-ng:crc16              79       10284.8700
m5.24xlarge  stress-ng:crc16              80       10392.3300
m5.24xlarge  stress-ng:crc16              81       10489.5500
m5.24xlarge  stress-ng:crc16              82       10609.9500
m5.24xlarge  stress-ng:crc16              83       10660.9400
m5.24xlarge  stress-ng:crc16              84       10819.9800
m5.24xlarge  stress-ng:crc16              85       10931.2500
m5.24xlarge  stress-ng:crc16              86       11042.3300
m5.24xlarge  stress-ng:crc16              87       11142.7500
m5.24xlarge  stress-ng:crc16              88       11259.1200
m5.24xlarge  stress-ng:crc16              89       11366.6500
m5.24xlarge  stress-ng:crc16              90       11432.5700
m5.24xlarge  stress-ng:crc16              91       11569.4600
m5.24xlarge  stress-ng:crc16              92       11680.7600
m5.24xlarge  stress-ng:crc16              93       11787.9300
m5.24xlarge  stress-ng:crc16              94       11902.5500
m5.24xlarge  stress-ng:crc16              95       11995.5200
m5.24xlarge  stress-ng:crc16              96       12102.4500
```
Here you can see how scalable is that instance (mainly the hypervisor/CPU and of
course the OS).

#### Getting performance/price results

The main reason for this program to exist is to conduct a performance/price ratio
for the benchmarked instances in order to know which instances should we use for
executing large batch jobs.

You can list the instances' relative performance/price results with a command
similar to this:

```
$ cloudperf performance  --filter benchmark_id=stress-ng:crc16 --filter region=us-west-2
instanceType     benchmark_id  benchmark_cpus  perf/price   price  benchmark_score     region     spot-az
[...]
  t2.2xlarge  stress-ng:crc16               8   8765.0808  0.1114         976.4300  us-west-2  us-west-2b
  t2.2xlarge  stress-ng:crc16               8   8765.0808  0.1114         976.4300  us-west-2  us-west-2a
   t2.xlarge  stress-ng:crc16               4   8862.2980  0.0557         493.6300  us-west-2  us-west-2a
   t2.xlarge  stress-ng:crc16               4   8862.2980  0.0557         493.6300  us-west-2  us-west-2b
   t2.xlarge  stress-ng:crc16               4   8862.2980  0.0557         493.6300  us-west-2  us-west-2c
   t3.xlarge  stress-ng:crc16               4   9067.4651  0.0501         454.2800  us-west-2  us-west-2b
  c4.8xlarge  stress-ng:crc16              36   9370.8534  0.4992        4677.9300  us-west-2  us-west-2c
  c4.8xlarge  stress-ng:crc16              36   9529.2931  0.4909        4677.9300  us-west-2  us-west-2b
  c4.8xlarge  stress-ng:crc16              36   9535.1203  0.4906        4677.9300  us-west-2  us-west-2a
  t3.2xlarge  stress-ng:crc16               8   9742.1769  0.1029        1002.4700  us-west-2  us-west-2a
  t3.2xlarge  stress-ng:crc16               8  10004.6906  0.1002        1002.4700  us-west-2  us-west-2b
    t3.small  stress-ng:crc16               2  12400.0000  0.0209         259.1600  us-west-2  us-west-2d
    t3.small  stress-ng:crc16               2  12459.6154  0.0208         259.1600  us-west-2        None
   t2.medium  stress-ng:crc16               2  17940.2878  0.0139         249.3700  us-west-2  us-west-2c
   t2.medium  stress-ng:crc16               2  17940.2878  0.0139         249.3700  us-west-2  us-west-2b
   t2.medium  stress-ng:crc16               2  17940.2878  0.0139         249.3700  us-west-2  us-west-2a
    t3.small  stress-ng:crc16               2  41136.5079  0.0063         259.1600  us-west-2  us-west-2a
    t3.small  stress-ng:crc16               2  41136.5079  0.0063         259.1600  us-west-2  us-west-2b
    t3.small  stress-ng:crc16               2  41136.5079  0.0063         259.1600  us-west-2  us-west-2c
```

Here you can see if nothing more is important to you than to get decent performance
for your money, t3.small would be the best.
_WARNING! The benchmarks are executed with unlimited CPU credits (where applicable),
but this is not reflected in the prices!_

Excluding burstable instances from the list gives:
```
c5d.18xlarge  stress-ng:crc16              72  14177.0380  0.7029        9965.0400       us-east-2       us-east-2b
 c5.18xlarge  stress-ng:crc16              72  14339.3896  0.6946        9960.1400       us-east-2       us-east-2c
 c5.18xlarge  stress-ng:crc16              72  14368.3497  0.6932        9960.1400       us-east-2       us-east-2b
 c5d.2xlarge  stress-ng:crc16               8  14375.2618  0.0764        1098.2700       us-east-2       us-east-2b
  c4.4xlarge  stress-ng:crc16              16  14386.1878  0.1448        2083.1200       us-east-2       us-east-2c
  c4.4xlarge  stress-ng:crc16              16  14386.1878  0.1448        2083.1200       us-east-2       us-east-2b
  c4.4xlarge  stress-ng:crc16              16  14386.1878  0.1448        2083.1200       us-east-2       us-east-2a
 c5d.2xlarge  stress-ng:crc16               8  14450.9211  0.0760        1098.2700       us-east-2       us-east-2c
  c5.4xlarge  stress-ng:crc16              16  14595.0690  0.1521        2219.9100       us-east-2       us-east-2a
  c5.4xlarge  stress-ng:crc16              16  14595.0690  0.1521        2219.9100       us-east-2       us-east-2c
  c5.4xlarge  stress-ng:crc16              16  14604.6711  0.1520        2219.9100       us-east-2       us-east-2b
 c5d.9xlarge  stress-ng:crc16              36  14605.6416  0.3421        4996.5900       us-east-2       us-east-2a
 c5d.9xlarge  stress-ng:crc16              36  14605.6416  0.3421        4996.5900       us-east-2       us-east-2b
 c5d.9xlarge  stress-ng:crc16              36  14605.6416  0.3421        4996.5900       us-east-2       us-east-2c
   a1.xlarge  stress-ng:crc16               4  15625.8883  0.0197         307.8300       us-east-2       us-east-2b
   a1.xlarge  stress-ng:crc16               4  15625.8883  0.0197         307.8300       us-east-2       us-east-2a
  c4.8xlarge  stress-ng:crc16              36  16153.0732  0.2896        4677.9300       us-east-2       us-east-2b
  c4.8xlarge  stress-ng:crc16              36  16153.0732  0.2896        4677.9300       us-east-2       us-east-2a
  c4.8xlarge  stress-ng:crc16              36  16153.0732  0.2896        4677.9300       us-east-2       us-east-2c
```
Which means at the time of writing, a spot c4.8xlarge instance is the winner
of the price/performance contest in the us-east-2 region.

## Currently available benchmarks

Because running benchmarks cost money, the range of them is quite limited ATM.
We use [stress-ng](https://kernel.ubuntu.com/~cking/stress-ng/) to do multiprocess
benchmarking. We don't really care about the absolute numbers just the relation
between them.

* `stress-ng:hdd_rndwr_512`: this writes 512 byte blocks with O_DIRECT, O_DSYNC flags
* `stress-ng:hdd_rndwr_4k`: this writes 4k byte blocks with O_DIRECT, O_DSYNC flags
* `stress-ng:crc16`: this computes 1024 rounds of CCITT CRC16 on random data
* `stress-ng:matrixprod`: matrix product of two 128 x 128 matrices of double floats

## Motivation

This script and running the benchmarks is sponsored by [System1](http://system1.com/).
System1 uses Amazon's infrastructure to run its business and has a lot of batch jobs,
which should be executed in the most cost effective manner.
Cloudperf helps to achieve that: it shows which is the most performing instance
for a given price at the time of the execution.

## Realtime data

The actual prices can be browsed here:
https://bra-fsn.github.io/cloudperf/prices.html
