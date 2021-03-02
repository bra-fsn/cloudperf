from __future__ import absolute_import
import base64
import re
import sys
import json
import time
import threading
import logging
import functools
import collections
from logging import NullHandler
import copy
from datetime import datetime, date
from io import StringIO
from multiprocessing.pool import ThreadPool
import boto3
import cachetools
import requests
import paramiko
import pandas as pd
from dateutil import parser
from botocore.exceptions import ClientError
from cloudperf.benchmarks import benchmarks
from cloudperf.core import sftp_write_file, DictQuery, set_fail_on_exit


session = boto3.session.Session()
logger = logging.getLogger(__name__)
logger.addHandler(NullHandler())

# get current defined-duration spot prices from here
spot_js = 'https://spot-price.s3.amazonaws.com/spotblocks-generic.js'

# blacklist instances (prefixes) until a given date (preview etc)
instance_blacklist = {'c6g': date(2020, 4, 1),
                      'm6g': date(2020, 2, 1),
                      'r6g': date(2020, 4, 1),
                      'cc2.8xlarge': date(9999, 1, 1),
                      }

# Self-destruct the machine after 2 hours
userdata_script = """#!/bin/sh
shutdown +120"""
ssh_keyname = 'batch'
ssh_user = 'ec2-user'
# metal instances may need a lot of time to start
ssh_get_conn_timeout = 30*60
ssh_exec_timeout = 600
ec2_specs = {'KeyName': ssh_keyname, 'SecurityGroups': ['tech-ssh'],
             'MaxCount': 1, 'MinCount': 1, 'Monitoring': {'Enabled': False},
             'InstanceInitiatedShutdownBehavior': 'terminate',
             'UserData': userdata_script,
             'TagSpecifications': [{'ResourceType': 'instance',
                                    'Tags': [{'Value': 'cloudperf', 'Key': 'Application'}]},
                                   {'ResourceType': 'volume',
                                    'Tags': [{'Value': 'cloudperf', 'Key': 'Application'}]}]}

instance_init_script = """#!/bin/sh
sudo systemctl stop acpid chronyd crond ecs postfix
sudo curl -L https://github.com/docker/compose/releases/download/1.23.2/docker-compose-`uname -s`-`uname -m` -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
"""


def boto3_paginate(method, **kwargs):
    client = method.__self__
    paginator = client.get_paginator(method.__name__)
    for page in paginator.paginate(**kwargs).result_key_iters():
        for result in page:
            yield result


def ping_region(region, latencies, lock):
    st = time.time()
    try:
        requests.get('http://ec2.{}.amazonaws.com/ping'.format(region), timeout=1)
    except Exception:
        return
    with lock:
        latencies[region] = time.time()-st


def aws_ping(regions):
    latencies = {}
    lock = threading.Lock()
    threads = []
    for region in regions:
        t = threading.Thread(target=ping_region, args=(region, latencies, lock))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return latencies


@cachetools.cached(cache={})
def aws_get_secret(name):
    sm = session.client('secretsmanager', region_name=aws_get_region())
    res = sm.get_secret_value(SecretId=name)
    return res['SecretString']


def aws_get_cpu_arch(instance):
    # XXX: maybe in the future Amazon will indicate the exact CPU architecture,
    # but until that...
    physproc = DictQuery(instance).get(['product', 'attributes', 'physicalProcessor'], '').lower()
    procarch = DictQuery(instance).get(['product', 'attributes', 'processorArchitecture'], '').lower()
    instance_type = DictQuery(instance).get(['product', 'attributes', 'instanceType'], '').lower()
    if re.match('^a[0-9]+\.', instance_type) or re.search('aws\s+(graviton.*|)\s*processor', physproc):
        # try to find arm instances
        return 'arm64'

    return 'x86_64'


def aws_get_region():
    region = boto3.session.Session().region_name
    if region:
        return region
    try:
        r = requests.get(
            'http://169.254.169.254/latest/dynamic/instance-identity/document')
        return r.json().get('region')
    except Exception:
        return None


def aws_newest_image(imgs):
    latest = None

    for image in imgs:
        if not latest:
            latest = image
            continue

        if parser.parse(image['CreationDate']) > parser.parse(latest['CreationDate']):
            latest = image

    return latest


@cachetools.cached(cache={})
def aws_get_latest_ami(name='amzn2-ami-ecs-hvm*ebs', arch='x86_64'):
    ec2 = session.client('ec2', region_name=aws_get_region())

    filters = [
        {'Name': 'name', 'Values': [name]},
        {'Name': 'description', 'Values': ['Amazon Linux AMI*']},
        {'Name': 'architecture', 'Values': [arch]},
        {'Name': 'owner-alias', 'Values': ['amazon']},
        {'Name': 'state', 'Values': ['available']},
        {'Name': 'root-device-type', 'Values': ['ebs']},
        {'Name': 'virtualization-type', 'Values': ['hvm']},
        {'Name': 'image-type', 'Values': ['machine']}
    ]

    response = ec2.describe_images(Owners=['amazon'], Filters=filters)
    return aws_newest_image(response['Images'])


def get_running_ec2_instances(filters=[]):
    ec2 = session.client('ec2', region_name=aws_get_region())
    response = ec2.describe_instances(Filters=filters)
    instances = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            if DictQuery(instance).get(['State', 'Name']) == 'running':
                instances.append(instance)
    return instances


def terminate_instances():
    filter = [{'Name': 'tag:Application', 'Values': ['cloudperf']}]
    tag = {'Key': 'Application', 'Value': 'cloudperf'}
    ec2 = session.client('ec2', region_name=aws_get_region())
    for instance in get_running_ec2_instances(filter):
        # although we filter for our tag, an error in this would cause the
        # termination of other machines, so do a manual filtering here as well
        if tag not in instance['Tags']:
            continue
        logger.info("Terminating instance {}".format(instance['InstanceId']))
        ec2.terminate_instances(InstanceIds=[instance['InstanceId']])


@cachetools.cached(cache={}, key=tuple)
def closest_regions(regions):
    latencies = aws_ping(regions)
    regions.sort(key=lambda k: latencies.get(k, 9999))
    return regions


def aws_format_memory(memory):
    return "{:,g} GiB".format(float(memory))


def aws_parse_memory(memory):
    # currently only GiBs are returned, so we don't need to take unit into account
    number, unit = memory.split()
    return float(number.replace(',', ''))


@cachetools.cached(cache={})
def get_region():
    region = boto3.session.Session().region_name
    if region:
        return region
    try:
        r = requests.get(
            'http://169.254.169.254/latest/dynamic/instance-identity/document')
        return r.json().get('region')
    except Exception:
        return None


@cachetools.cached(cache={})
def get_regions():
    client = session.client('ec2')
    return [region['RegionName'] for region in client.describe_regions()['Regions']]


@cachetools.cached(cache={})
def get_ec2_instances(**filter_opts):
    """Get AWS instances according to the given filter criteria

    Args:
        any Field:Value pair which the AWS API accepts.
        Example from a c5.4xlarge instance:
        {'capacitystatus': 'Used',
         'clockSpeed': '3.0 Ghz',
         'currentGeneration': 'Yes',
         'dedicatedEbsThroughput': 'Upto 2250 Mbps',
         'ecu': '68',
         'enhancedNetworkingSupported': 'Yes',
         'instanceFamily': 'Compute optimized',
         'instanceType': 'c5.4xlarge',
         'licenseModel': 'No License required',
         'location': 'US West (Oregon)',
         'locationType': 'AWS Region',
         'memory': '32 GiB',
         'networkPerformance': 'Up to 10 Gigabit',
         'normalizationSizeFactor': '32',
         'operatingSystem': 'Linux',
         'operation': 'RunInstances:0004',
         'physicalProcessor': 'Intel Xeon Platinum 8124M',
         'preInstalledSw': 'SQL Std',
         'processorArchitecture': '64-bit',
         'processorFeatures': 'Intel AVX, Intel AVX2, Intel AVX512, Intel Turbo',
         'servicecode': 'AmazonEC2',
         'servicename': 'Amazon Elastic Compute Cloud',
         'storage': 'EBS only',
         'tenancy': 'Host',
         'usagetype': 'USW2-HostBoxUsage:c5.4xlarge',
         'vcpu': '16'}

    Returns:
        type: dict of AWS product descriptions

    """
    filters = [{'Type': 'TERM_MATCH', 'Field': k, 'Value': v}
               for k, v in filter_opts.items()]

    # currently the pricing API is limited to some regions, so don't waste time
    # on trying to access it on others one by one
    # regions = get_regions()
    regions = ['us-east-1', 'ap-south-1']
    for region in closest_regions(regions):
        pricing = session.client('pricing', region_name=region)
        instances = []
        for data in boto3_paginate(pricing.get_products, ServiceCode='AmazonEC2', Filters=filters, MaxResults=100):
            pd = json.loads(data)
            instances.append(pd)
        break
    return instances


def get_ec2_defined_duration_prices():
    """Get AWS defined-duration prices from the web. Currently there's no
    API for this, so we'll use the JavaScript used by the public EC2 spot
    pricing page: https://aws.amazon.com/ec2/spot/pricing/
    We deliberately lack error handling here, so we can detect any failures in
    the parsing process.
    """

    r = requests.get(spot_js)
    # this is JavaScript, so we have to parse data out from it
    js = r.text
    data = json.loads(js[js.find('{'):js.rfind('}')+1])

    # create a structure of region:instance_type:duration prices similar to this:
    # {'us-west-2': {'g4dn.xlarge': {1: 0.307,
    #                                2: 0.335,
    #                                3: 0.349,
    #                                4: 0.363,
    #                                5: 0.377,
    #                                6: 0.391}}}
    # the keys in the instance's dictionary is the duration in hours, where
    # we fill up the missing durations in the input data with a linear estimation
    block_data = collections.defaultdict(lambda: collections.defaultdict(dict))
    for region_data in data['config']['regions']:
        region = region_data['region']
        for instance_data in region_data['instanceTypes']:
            for instance in instance_data['sizes']:
                instance_type = instance['size']
                for duration_data in instance['valueColumns']:
                    # name is like '1 hour' or '6 hours'
                    m = re.search('[0-9]+', duration_data['name'])
                    if not m:
                        continue
                    duration = int(m.group(0))
                    block_data[region][instance_type][duration] = float(duration_data['prices']['USD'])
        # fill up gaps in defined durations by estimating the hourly price
        for instance_type, instance_data in block_data[region].items():
            min_duration = min(instance_data.keys())
            max_duration = max(instance_data.keys())
            min_price = instance_data[min_duration]
            max_price = instance_data[max_duration]
            step = (max_price-min_price)/max_duration
            for i in range(min_duration, max_duration):
                if i in instance_data:
                    continue
                # round to 3 digits precision
                instance_data[i] = round(min_price+step*i, 3)

    return block_data


def get_ec2_prices(fail_on_missing_regions=False, **filter_opts):
    """Get AWS instance prices according to the given filter criteria

    Args:
        get_instance_types arguments

    Returns:
        DataFrame with instance attributes and pricing

    """
    from cloudperf.providers.aws import region_map, location_map
    prices = []
    params = {}

    missing_regions = set()
    for data in get_ec2_instances(**filter_opts):
        try:
            instance_type = data['product']['attributes']['instanceType']
            price = float(list(list(data['terms']['OnDemand'].values())[
                          0]['priceDimensions'].values())[0]['pricePerUnit']['USD'])
        except Exception:
            continue
        if price == 0:
            continue
        if data['product']['attributes']['memory'] == 'NA' or \
                data['product']['attributes']['vcpu'] == 'NA':
            # skip these
            continue
        vcpu = int(data['product']['attributes']['vcpu'])
        memory = aws_parse_memory(data['product']['attributes']['memory'])
        try:
            region = region_map[data['product']['attributes']['location']]
        except KeyError:
            missing_regions.add(data['product']['attributes']['location'])
        params[instance_type] = data['product']['attributes']
        params[instance_type].update({'vcpu': vcpu, 'memory': memory, 'region': region,
                                      'cpu_arch': aws_get_cpu_arch(data),
                                      'date': datetime.now()})
        d = {'price': price, 'spot': False, 'spot-az': None}
        d.update(params[instance_type])
        prices.append(d)

    if fail_on_missing_regions and missing_regions:
        print('The following regions are missing from aws.region_map, please '
              'update (for eg. from https://aws.amazon.com/ec2/pricing/on-demand/, '
              'inspecting the region dropdown, or '
              'https://docs.aws.amazon.com/general/latest/gr/rande.html)')
        print(*missing_regions, sep='\n')
        sys.exit(1)

    if not prices:
        # we couldn't find any matching instances
        return prices

    # get actual defined-duration spot prices from the web, until the pricing
    # API supports these...
    block_prices = get_ec2_defined_duration_prices()

    for region in get_regions():
        ec2 = session.client('ec2', region_name=region)
        for data in boto3_paginate(ec2.describe_spot_price_history, InstanceTypes=list(params.keys()),
                                   MaxResults=100, ProductDescriptions=['Linux/UNIX (Amazon VPC)'], StartTime=datetime.now()):
            instance_type = data['InstanceType']
            d = copy.deepcopy(params[instance_type])
            d.update({'price': float(data['SpotPrice']), 'spot': True, 'spot-az': data['AvailabilityZone'], 'region': region})
            d.update({'location': location_map[region]})
            for duration, price in DictQuery(block_prices).get([region, instance_type], {}).items():
                # add spot blocked duration prices, if any
                d.update({f'price_{duration}h': price})
            prices.append(d)

    return pd.DataFrame.from_dict(prices)


def get_ssh_connection(instance, user, pkey, timeout):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    start = time.time()
    while start+timeout > time.time():
        try:
            ssh.connect(instance['PrivateIpAddress'], username=user, pkey=pkey, timeout=10, auth_timeout=10)
            break
        except Exception as e:
            logger.info("Couldn't connect: {}, retrying for {:.0f}s".format(e, start+timeout-time.time()))
            time.sleep(5)
    else:
        return None
    return ssh


def log_exception(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            err = "Exception in {}".format(function.__name__)
            logging.exception(err)
    return wrapper


@log_exception
def run_benchmarks(args):
    threading.current_thread().name = 'run_bench'
    ami, instance, tags, benchmarks_to_run = args
    specs = copy.deepcopy(ec2_specs)
    # extend tagspecs with user specified tags
    tagspecs = [{'Key': k, 'Value': v} for k, v in tags]
    for i in specs.get('TagSpecifications', []):
        i['Tags'].extend(tagspecs)
    bdmap = ami['BlockDeviceMappings']
    try:
        # You cannot specify the encrypted flag if specifying a snapshot id in a block device mapping.
        del bdmap[0]['Ebs']['Encrypted']
    except Exception:
        pass
    specs.update({'BlockDeviceMappings': bdmap,
                  'ImageId': ami['ImageId'], 'InstanceType': instance.instanceType})
    # add unlimited cpu credits on burstable type instances, so these won't affect
    # benchmark results
    if re.match('^t[0-9]+\.', instance.instanceType):
        specs.update({'CreditSpecification': {'CpuCredits': 'unlimited'}})
    spotspecs = copy.deepcopy(specs)
    spotspecs.update({'InstanceMarketOptions': {'MarketType': 'spot',
                                                'SpotOptions': {
                                                    'MaxPrice': str(instance.price),
                                                    'SpotInstanceType': 'one-time',
                                                    'InstanceInterruptionBehavior': 'terminate'
                                                    }
                                                }})
    # start with a spot instance
    create_specs = spotspecs
    retcount = 0
    ec2_inst = None
    ec2 = session.client('ec2', region_name=aws_get_region())
    while retcount < 16:
        try:
            ec2_inst = ec2.run_instances(**create_specs)['Instances'][0]
            break
        except ClientError as e:
            # retry on request limit exceeded
            if e.response['Error']['Code'] == 'RequestLimitExceeded':
                logger.info("Request limit for {}: {}, retry #{}".format(instance.instanceType,
                                                                           e.response['Error']['Message'], retcount))
                time.sleep(1.2**retcount)
                retcount += 1
                continue

            if e.response['Error']['Code'] == 'InsufficientInstanceCapacity':
                logger.info('Insufficient capacity for {}: {}'.format(
                    instance.instanceType, e))
                if create_specs == specs:
                    # if it was on-demand retry until the counter expires
                    time.sleep(1.2**retcount)
                    retcount += 1
                else:
                    # retry with on demand if this was with spot
                    create_specs = specs
                    retcount = 0
                continue

            if e.response['Error']['Code'] == 'SpotMaxPriceTooLow':
                try:
                    # the actual spot price is the second, extract it
                    sp = re.findall('[0-9]+\.[0-9]+',
                                    e.response['Error']['Message'])[1]
                    logger.info(
                        "Spot price too low spotmax:{}, current price:{}".format(instance.price, sp))
                except Exception:
                    logger.info("Spot price too low for {}, {}".format(
                        instance.instanceType, e.response['Error']['Message']))
                # retry with on demand
                create_specs = specs
                retcount = 0
                continue

            if e.response['Error']['Code'] == 'MissingParameter':
                # this can't be fixed, exit
                logger.error("Missing parameter while creating {}: {}".format(
                    instance.instanceType, e))
                set_fail_on_exit()
                break

            if e.response['Error']['Code'] == 'InvalidParameterValue':
                # certain instances are not allowed to be created
                logger.error("Error starting instance {}: {}".format(
                    instance.instanceType, e.response['Error']['Message']))
                if retcount == 0:
                    # retry with on demand
                    create_specs = specs
                    retcount += 1
                    continue
                set_fail_on_exit()
                break

            if e.response['Error']['Code'] == 'Unsupported':
                # certain instances are not allowed to be created
                logger.error("Unsupported instance {}: {}, specs: {}".format(
                    instance.instanceType, e.response['Error']['Message'],
                    base64.b64encode(json.dumps(create_specs).encode('utf-8'))))
                break

            if e.response['Error']['Code'] == 'InstanceCreditSpecification.NotSupported':
                # remove unlimited credit and try again
                logger.error("{} doesn't support unlimited credits: {}".format(
                    instance.instanceType, e.response['Error']['Message']))
                if 'CreditSpecification' in create_specs:
                    del create_specs['CreditSpecification']
                    retcount += 1
                    continue
                else:
                    break

            logger.error("Other error while creating {}: {}, code: {}".format(
                instance.instanceType, e, DictQuery(e.response).get(['Error', 'Code'])))
            time.sleep(1.2**retcount)
            retcount += 1

        except Exception as e:
            logger.error("Other exception while creating {}: {}".format(
                instance.instanceType, e))
            time.sleep(1.2**retcount)
            retcount += 1

    if not ec2_inst:
        return None

    instance_id = ec2_inst['InstanceId']
    threading.current_thread().name = instance_id

    logger.info(
        "Waiting for instance {} to be ready. AMI: {}".format(instance.instanceType, ami))
    # wait for the instance
    try:
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={
            # wait for up to 30 minutes
            'Delay': 15,
            'MaxAttempts': 120
            })
    except Exception:
        logger.exception(
            'Waiter failed for {}'.format(instance.instanceType))

    # give 5 secs before trying ssh
    time.sleep(5)
    pkey = paramiko.RSAKey.from_private_key(
        StringIO(aws_get_secret('ssh_keys/{}'.format(ssh_keyname))))
    ssh = get_ssh_connection(ec2_inst, ssh_user, pkey, ssh_get_conn_timeout)
    if ssh is None:
        logger.error("Couldn't open an ssh connection, terminating instance")
        ec2.terminate_instances(InstanceIds=[instance_id])
        return None

    sftp = ssh.open_sftp()

    # write init_script
    for i in range(4):
        try:
            sftp_write_file(sftp, 'init_script', instance_init_script)
            break
        except Exception:
            logger.exception("Failed to write init_script, try #{}".format(i))
            continue
    # try stop all unnecessary services in order to provide a more reliable result
    for i in range(4):
        logger.info("Trying to execute init_script, try #{}".format(i))
        stdin, stdout, stderr = ssh.exec_command("./init_script", timeout=ssh_exec_timeout)
        if stdout.channel.recv_exit_status() == 0:
            break
        time.sleep(5)
    else:
        logger.error("Couldn't execute init_script: {}, {}".format(
            stdout.read(), stderr.read()))
        ec2.terminate_instances(InstanceIds=[instance_id])
        return None

    # give some more time for the machine to be ready and to settle down
    time.sleep(20)

    results = []
    try:
        for name, bench_data in benchmarks_to_run.items():
            threading.current_thread().name = '{}/{}'.format(instance_id, name)
            docker_img = bench_data['images'].get(instance.cpu_arch, None)
            if not docker_img:
                logger.error("Couldn't find docker image for {}/{}".format(name, instance.cpu_arch))
                continue
            # write files for the benchmark
            for name, contents in bench_data['images'].get('files', {}):
                sftp_write_file(sftp, name, contents)

            # docker pull and wait some time
            for i in range(4):
                logger.info("Docker pull, try #{}".format(i))
                stdin, stdout, stderr = ssh.exec_command("docker pull {}; sync; sleep 10".format(docker_img), timeout=ssh_exec_timeout)
                if stdout.channel.recv_exit_status() == 0:
                    break
                time.sleep(5)
            else:
                logger.error("Couldn't pull docker image {}, {}".format(
                    stdout.read(), stderr.read()))
                continue

            if 'composefile' in bench_data:
                sftp_write_file(sftp, 'docker-compose.yml', bench_data['composefile'], 0o644)
                # start docker compose
                stdin, stdout, stderr = ssh.exec_command("docker-compose up -d", timeout=ssh_exec_timeout)
                if stdout.channel.recv_exit_status() != 0:
                    logger.error("Couldn't start docker compose {}, {}".format(
                        stdout.read(), stderr.read()))
                    continue

                if 'after_compose_up' in bench_data:
                    sftp_write_file(sftp, 'after_compose_up', bench_data['after_compose_up'])
                    stdin, stdout, stderr = ssh.exec_command("./after_compose_up", timeout=ssh_exec_timeout)
                    if stdout.channel.recv_exit_status() != 0:
                        logger.error("Couldn't start after_compose_up script {}, {}".format(
                            stdout.read(), stderr.read()))
                        continue

            if 'cpus' in bench_data and bench_data['cpus']:
                cpulist = bench_data['cpus']
            else:
                cpulist = range(1, instance.vcpu+1)

            # default options if missing
            docker_opts = bench_data.get('docker_opts', '--network none')
            for i in cpulist:
                ssh.exec_command("sync", timeout=ssh_exec_timeout)
                dcmd = bench_data['cmd'].format(numcpu=i)
                if 'timeout' in bench_data:
                    timeout_cmd = 'timeout -k {} {} '.format(bench_data['timeout']+5, bench_data['timeout'])
                else:
                    timeout_cmd = ''
                cmd = '{}docker run --rm {} {} {}'.format(timeout_cmd, docker_opts, docker_img, dcmd)
                scores = []
                for it in range(bench_data.get('iterations', 3)):
                    logger.info("Running command: {}, iter: #{}".format(cmd, it))
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=ssh_exec_timeout)
                    ec = stdout.channel.recv_exit_status()
                    stdo = stdout.read()
                    stdrr = stderr.read()
                    if ec == 0:
                        try:
                            scores.append(float(stdo))
                        except Exception:
                            logger.info(
                                "Couldn't parse output: {}".format(stdo))
                            scores.append(None)
                    else:
                        logger.info("Non-zero exit code {}, {}, {}".format(ec, stdo, stdrr))
                aggr_f = bench_data.get('score_aggregation', max)
                try:
                    score = aggr_f(scores)
                except Exception:
                    score = None
                results.append({'instanceType': instance.instanceType,
                                'benchmark_cpus': i, 'benchmark_score': score, 'benchmark_id': name,
                                'benchmark_name': bench_data.get('name'),
                                'benchmark_cmd': cmd, 'benchmark_program': bench_data.get('program'),
                                'date': datetime.now()})
            if 'composefile' in bench_data:
                stdin, stdout, stderr = ssh.exec_command("docker-compose down -v", timeout=ssh_exec_timeout)
                if stdout.channel.recv_exit_status() != 0:
                    logger.error("Couldn't stop docker compose: {}, {}".format(
                        stdout.read(), stderr.read()))
                    continue
                if 'after_compose_down' in bench_data:
                    sftp_write_file(sftp, 'after_compose_down', bench_data['after_compose_down'])
                    stdin, stdout, stderr = ssh.exec_command("./after_compose_down", timeout=ssh_exec_timeout)
                    if stdout.channel.recv_exit_status() != 0:
                        logger.error("Couldn't start after_compose_down script: {}, {}".format(
                            stdout.read(), stderr.read()))
                        continue
    except Exception:
        logger.exception("Error while executing benchmarks")

    logger.info("Finished with instance, terminating")
    ec2.terminate_instances(InstanceIds=[instance_id])
    if results:
        return pd.DataFrame.from_dict(results)
    else:
        return None


def get_benchmarks_to_run(instance, perf_df, expire):
    my_benchmarks = copy.deepcopy(benchmarks)
    # filter the incoming perf data only to our instance type
    perf_df = perf_df[perf_df['instanceType'] == instance.instanceType][['instanceType', 'benchmark_id', 'date']].drop_duplicates()
    for idx, row in perf_df.iterrows():
        if (datetime.now() - row.date).seconds >= expire:
            # leave the benchmark if it's not yet expired ...
            continue
        # ... and drop, if it is
        my_benchmarks.pop(row.benchmark_id, None)

    return my_benchmarks


def is_blacklisted(instance):
    for prefix, dt in instance_blacklist.items():
        if instance.startswith(prefix) and datetime.now().date() <= dt:
            return True
    return False


def get_ec2_performance(prices_df, perf_df=None, update=None, expire=None, tags=[], **filter_opts):
    # drop spot instances
    prices_df = prices_df.drop(prices_df[prices_df.spot == True].index)
    # remove duplicate instances, so we'll have a list of all on-demand instances
    prices_df = prices_df.drop_duplicates(subset='instanceType')

    bench_args = []
    for instance in prices_df.itertuples():
        if is_blacklisted(instance.instanceType):
            logger.info("Skipping blacklisted instance: {}".format(instance.instanceType))
            continue
        ami = aws_get_latest_ami(arch=instance.cpu_arch)
        if perf_df is not None and update:
            benchmarks_to_run = get_benchmarks_to_run(instance, perf_df, expire)
        else:
            benchmarks_to_run = benchmarks

        if not benchmarks_to_run:
            logger.info("Skipping already benchmarked instance: {}".format(instance.instanceType))
            # leave this instance out if there is no benchmark to run
            continue
        ami = aws_get_latest_ami(arch=instance.cpu_arch)
        bench_args.append([ami, instance, tags, benchmarks_to_run])
    if bench_args:
        pool = ThreadPool(4)
        results = [res for res in pool.map(run_benchmarks, bench_args) if res is not None]
        if results:
            return pd.concat(results, ignore_index=True, sort=False)
    return pd.DataFrame({})
