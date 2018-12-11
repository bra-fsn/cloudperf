from __future__ import absolute_import
import json
import time
import threading
import copy
from datetime import datetime
import boto3
import cachetools
import requests
import pandas as pd


session = boto3.session.Session()

# static map until Amazon can provide the name in boto3 along with the region
# code...
region_map = {
    'Asia Pacific (Mumbai)': 'ap-south-1',
    'Asia Pacific (Seoul)': 'ap-northeast-2',
    'Asia Pacific (Singapore)': 'ap-southeast-1',
    'Asia Pacific (Sydney)': 'ap-southeast-2',
    'Asia Pacific (Tokyo)': 'ap-northeast-1',
    'Canada (Central)': 'ca-central-1',
    'EU (Frankfurt)': 'eu-central-1',
    'EU (Ireland)': 'eu-west-1',
    'EU (London)': 'eu-west-2',
    'EU (Paris)': 'eu-west-3',
    'South America (Sao Paulo)': 'sa-east-1',
    'US East (N. Virginia)': 'us-east-1',
    'US East (Ohio)': 'us-east-2',
    'AWS GovCloud (US)': 'us-gov-west-1',
    'AWS GovCloud (US-West)': 'us-gov-west-1',
    'AWS GovCloud (US-East)': 'us-gov-east-1',
    'US West (N. California)': 'us-west-1',
    'US West (Oregon)': 'us-west-2'}


class DictQuery(dict):
    def get(self, keys, default=None):
        val = None

        for key in keys:
            if val:
                if isinstance(val, list):
                    val = [v.get(key, default) if v else None for v in val]
                else:
                    try:
                        val = val.get(key, default)
                    except AttributeError:
                        return default
            else:
                val = dict.get(self, key, default)

            if val == default:
                break

        return val


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


def aws_get_cpu_arch(instance):
    # XXX: maybe in the future Amazon will indicate the exact CPU architecture,
    # but until that...
    physproc = DictQuery(instance).get(['product', 'attributes', 'physicalProcessor'], '').lower()
    procarch = DictQuery(instance).get(['product', 'attributes', 'processorArchitecture'], '').lower()
    if physproc == 'aws processor' and procarch == '64-bit':
        return 'arm64'
    return 'x86_64'


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
        try:
            for data in boto3_paginate(pricing.get_products, ServiceCode='AmazonEC2', Filters=filters, MaxResults=100):
                pd = json.loads(data)
                instances.append(pd)
            break
        except Exception:
            continue
    return instances


def get_ec2_prices(**filter_opts):
    """Get AWS instance prices according to the given filter criteria

    Args:
        get_instance_types arguments

    Returns:
        DataFrame with instance attributes and pricing

    """
    prices = []
    params = {}

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
        region = region_map.get(data['product']['attributes']['location'])
        params[instance_type] = data['product']['attributes']
        params[instance_type].update({'vcpu': vcpu, 'memory': memory, 'region': region, 'cpu_arch': aws_get_cpu_arch(data)})
        d = {'price': price, 'spot': False, 'spot-az': None}
        d.update(params[instance_type])
        prices.append(d)

    if not prices:
        # we couldn't find any matching instances
        return prices

    for region in get_regions():
        ec2 = session.client('ec2', region_name=region)
        for data in boto3_paginate(ec2.describe_spot_price_history, InstanceTypes=list(params.keys()),
                                   MaxResults=100, ProductDescriptions=['Linux/UNIX (Amazon VPC)'], StartTime=datetime.now()):
            instance_type = data['InstanceType']
            d = copy.deepcopy(params[instance_type])
            d.update({'price': float(data['SpotPrice']), 'spot': True, 'spot-az': data['AvailabilityZone'], 'region': region})
            prices.append(d)

    return pd.DataFrame.from_dict(prices)


def get_ec2_performance(**filter_opts):
    pass
