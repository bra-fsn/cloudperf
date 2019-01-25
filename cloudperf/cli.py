import os
import click
import pandas as pd
import pytimeparse
import boto3
from cloudperf import get_prices, get_performance, prices_url, performance_url


@click.group()
def main():
    pass


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--file', help='Write prices to this file', required=True)
@click.option('--s3-bucket', help='Write prices to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
def write_prices(prices, file, s3_bucket, update):
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
    get_prices(prices, update).to_json(file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(s3_bucket)
        bucket.upload_file(file, os.path.basename(file), ExtraArgs={'ACL':'public-read'})


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--file', help='Write performance data to this file', required=True)
@click.option('--s3-bucket', help='Write prices to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
@click.option('--expire', help='Re-run benchmarks after this time', default='12w', show_default=True)
def write_performance(prices, perf, file, s3_bucket, update, expire):
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
    # convert human readable to seconds
    expire = pytimeparse.parse(expire)
    if update:
        get_performance(prices, perf, update, expire).to_json(file, orient='records', compression=comp, date_unit='s')
    else:
        get_performance(prices, None, update, expire).to_json(file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(s3_bucket)
        bucket.upload_file(file, os.path.basename(file), ExtraArgs={'ACL':'public-read'})


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--cols', help='Columns to show', default=['instanceType', 'region', 'spot-az',
                                                         'vcpu', 'memory', 'price'],
              show_default=True, multiple=True)
@click.option('--sort', help='Sort by these columns', default=['price'], multiple=True, show_default=True)
def prices(prices, cols, sort):
    df = get_prices(prices)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--cols', help='Columns to show', default=['instanceType', 'benchmark_id', 'benchmark_cpus',
                                                         'benchmark_score'],
              show_default=True, multiple=True)
@click.option('--sort', help='Sort by these columns', default=['benchmark_score'], multiple=True, show_default=True)
def performance(prices, perf, cols, sort):
    df = get_performance(prices, perf)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))
