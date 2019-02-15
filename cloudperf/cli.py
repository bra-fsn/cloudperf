import os
import click
import pandas as pd
import pytimeparse
import boto3
from cloudperf import get_prices, get_performance, get_combined, prices_url, performance_url


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


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--file', help='Write prices to this file', required=True)
@click.option('--s3-bucket', help='Write prices to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
def write_prices(prices, file, s3_bucket, update):
    if not update:
        prices = None
    df = get_prices(prices, update)
    df.to_json(file, orient='records', compression=get_comp(file), date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, file)


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--file', help='Write performance data to this file', required=True)
@click.option('--s3-bucket', help='Write data to this s3 bucket')
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
@click.option('--expire', help='Re-run benchmarks after this time', default='12w', show_default=True)
def write_performance(prices, perf, file, s3_bucket, update, expire):
    # convert human readable to seconds
    expire = pytimeparse.parse(expire)
    comp = get_comp(file)
    if not update:
        perf = None
    get_performance(prices, perf, update, expire).to_json(file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, file)


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--file', help='Write combined perf/price data to this file', required=True)
@click.option('--s3-bucket', help='Write data to this s3 bucket')
def write_combined(prices, perf, file, s3_bucket):
    comp = get_comp(file)
    get_combined(prices, perf).to_json(file, orient='records', compression=comp, date_unit='s')
    if s3_bucket is not None:
        s3_upload(s3_bucket, file)


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


perf_defcols = ['instanceType', 'benchmark_id', 'benchmark_cpus']


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', default=prices_url, show_default=True)
@click.option('--perf', help='Performance URL (pandas.read_json)', default=performance_url, show_default=True)
@click.option('--cols', help='Columns to show', default=perf_defcols, show_default=True, multiple=True)
@click.option('--sort', help='Sort by these columns', default=['perf/price/cpu'], multiple=True, show_default=True)
@click.option('--combined/--no-combined',
              help='Show combined prices/performance data or just performance',
              default=True, show_default=True)
def performance(prices, perf, cols, sort, combined):
    cols = list(cols)
    if combined:
        df = get_combined(prices, perf)
        if set(cols) == set(perf_defcols):
            # if we're using the default columns, add perf/price/cpu and other
            # infos as well
            cols.extend(['perf/price/cpu', 'region', 'spot-az'])
            # keep order and remove duplicates
            seen = {}
            cols = [seen.setdefault(x, x) for x in cols if x not in seen]
    else:
        sort = ['benchmark_score']
        df = get_performance(prices, perf)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))
