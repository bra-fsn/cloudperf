import os
import re
import sys
import signal
import traceback
import click
import pandas as pd
import pytimeparse
import boto3
from cloudperf import get_prices, get_performance, get_combined, prices_url, performance_url, terminate_instances
from cloudperf.core import fail_on_exit

try:
    import faulthandler
    faulthandler.register(signal.SIGUSR1)
except ImportError:
    pass


@click.group()
def main():
    pass


def get_comp(file):
    fn, ext = os.path.splitext(file)
    comp = None
    try:
        ext = ext[1:]
        if ext in ('gzip', 'bz2', 'zip', 'xz'):
            comp = ext
        if ext == 'gz':
            comp = 'gzip'
    except Exception:
        pass
    return comp


def s3_upload(s3_bucket, file):
    comp = get_comp(file)
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket)
    if comp == 'gzip':
        # upload with gzip Content-Encoding and proper Content-Type
        bucket.upload_file(file, os.path.basename(file),
                           ExtraArgs={'ACL': 'public-read',
                                      'ContentType': 'application/json; charset=utf-8',
                                      'ContentEncoding': 'gzip'})
    elif comp:
        bucket.upload_file(file, os.path.basename(
            file), ExtraArgs={'ACL': 'public-read'})
    else:
        bucket.upload_file(file, os.path.basename(
            file), ExtraArgs={'ACL': 'public-read',
                              'ContentType': 'application/json; charset=utf-8'})


def df_filter(df, filters):
    for f in filters:
        m = re.search('(?P<col>[^=<>]+)(?P<op>[=<>]+)(?P<value>.*)', f)
        if not m:
            continue
        try:
            v = float(m.group('value'))
        except Exception:
            v = m.group('value')
        if m.group('op') == '=':
            df = df[df[m.group('col')] == v]
        elif m.group('op') == '>':
            df = df[df[m.group('col')] > v]
        elif m.group('op') == '<':
            df = df[df[m.group('col')] < v]
        elif m.group('op') == '<=':
            df = df[df[m.group('col')] <= v]
        elif m.group('op') == '>=':
            df = df[df[m.group('col')] >= v]
    return df


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--file', help='Write prices to this file', required=True)
@click.option('--s3-bucket', help='Write prices to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
@click.option('--fail-on-missing-regions/--no-fail-on-missing-regions',
              help='Fail if there are missing regions in the region map',
              default=False, show_default=True)
def write_prices(prices, file, s3_bucket, update, fail_on_missing_regions):
    if not update:
        prices = None
    df = get_prices(prices, update, fail_on_missing_regions=fail_on_missing_regions)
    df.to_json(file, orient='records', compression=get_comp(file), date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, file)
    if fail_on_exit():
        sys.exit(1)


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--file', help='Write performance data to this file', default='/tmp/performance.json.gz')
@click.option('--s3-bucket', help='Write data to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
@click.option('--expire', help='Re-run benchmarks after this time', default='12w', show_default=True)
@click.option('--terminate/--no-terminate',
              help='Terminate tagged images at the end of the run to clean up leftover ones',
              default=False, show_default=True)
@click.option('--tag', help='Add these tags to EC2 instances (key:value format)', multiple=True)
def write_performance(prices, perf, file, s3_bucket, update, expire, terminate, tag):
    tags = [i.split(':', 1) for i in tag]
    # convert human readable to seconds
    expire = pytimeparse.parse(expire)
    comp = get_comp(file)
    if not update:
        perf = None
    try:
        get_performance(prices, perf, update, expire, tags=tags).to_json(file, orient='records', compression=comp, date_unit='s')
        if s3_bucket is not None:
            s3_upload(s3_bucket, file)
    except Exception:
        traceback.print_exc()
    finally:
        if terminate:
            terminate_instances()
    if fail_on_exit():
        sys.exit(1)


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--file', help='Write combined perf/price data to this file', default='/tmp/combined.json.gz')
@click.option('--web-file', help='Write performance data for web serving to this file', default='/tmp/webperf.json')
@click.option('--s3-bucket', help='Write data to this s3 bucket')
def write_combined(prices, perf, file, web_file, s3_bucket):
    comp = get_comp(file)
    web_cols = ['instanceType', 'benchmark_id', 'vcpu', 'physicalProcessor']

    get_combined(prices, perf).to_json(file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, file)

    df = get_combined(prices, perf, maxcpu=True)
    comp = get_comp(web_file)
    # only keep these columns for the web file and also reduce
    # the output to one benchmark result per instance
    df = df[web_cols + ['benchmark_score']].drop_duplicates(subset=web_cols)
    df.to_json(web_file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, web_file)

    if fail_on_exit():
        sys.exit(1)


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--cols', help='Columns to show', default=['instanceType', 'region', 'spot-az',
                                                         'vcpu', 'memory', 'price'],
              show_default=True, multiple=True)
@click.option('--sort', help='Sort by these columns', default=['price'], multiple=True, show_default=True)
@click.option('--filter', help="Apply filters like --filter 'benchmark_cpus>4' --filter benchmark_id=sng_zlib", default=[], multiple=True)
def prices(prices, cols, sort, filter):
    df = get_prices(prices)
    df = df_filter(df, filter)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))


perf_defcols = ['instanceType', 'benchmark_id', 'benchmark_cpus']


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--cols', help='Columns to show', default=perf_defcols, show_default=True, multiple=True)
@click.option('--sort', help='Sort by these columns', default=['perf/price'], multiple=True, show_default=True)
@click.option('--filter', help="Apply filters like --filter 'benchmark_cpus>4' --filter benchmark_id=sng_zlib", default=[], multiple=True)
@click.option('--combined/--no-combined',
              help='Show combined prices/performance data or just performance',
              default=True, show_default=True)
@click.option('--maxcpu/--no-maxcpu',
              help='Show performance only for maximum number of CPUs',
              default=True, show_default=True)
def performance(prices, perf, cols, sort, filter, combined, maxcpu):
    cols = list(cols)
    if combined:
        df = get_combined(prices, perf, maxcpu)
        if set(cols) == set(perf_defcols):
            # if we're using the default columns, add perf/price and other
            # infos as well
            cols.extend(['perf/price', 'price', 'benchmark_score', 'region', 'spot-az'])
            # keep order and remove duplicates
            seen = {}
            cols = [seen.setdefault(x, x) for x in cols if x not in seen]
    else:
        sort = ['benchmark_score']
        df = get_performance(prices, perf, maxcpu=maxcpu)
        if set(cols) == set(perf_defcols):
            cols.extend(['benchmark_score'])
            seen = {}
            cols = [seen.setdefault(x, x) for x in cols if x not in seen]
    df = df_filter(df, filter)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.float_format', '{:.4f}'.format):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))
