import os
import click
import pandas as pd
from cloudperf import get_prices, get_performance


@click.group()
def main():
    pass


@main.command()
@click.option('--file', help='Write prices to this file', required=True)
@click.option('--update/--no-update',
              help='Read file first and update it with new data, leaving disappeared entries there for historical reasons',
              default=True, show_default=True)
def write_prices(file, update):
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
    get_prices(file, update).to_json(file, orient='records', compression=comp, date_unit='s')


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', required=True)
@click.option('--file', help='Write performance data to this file', required=True)
def write_performance(prices, file):
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
    get_performance(prices).to_json(file, orient='records', compression=comp, date_unit='s')


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)')
@click.option('--cols', help='Columns to show', default=['instanceType', 'region', 'spot-az',
                                                         'vcpu', 'memory', 'price'],
              show_default=True, multiple=True)
@click.option('--sort', help='Sort by this column', default=['price'], multiple=True, show_default=True)
def prices(prices, cols, sort):
    df = get_prices(prices)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))


@main.command()
@click.option('--prices', help='Prices URL (pandas.read_json)', required=True)
@click.option('--perf', help='Performance URL (pandas.read_json)')
@click.option('--cols', help='Columns to show', default=['instanceType', 'benchmark_id', 'benchmark_cpus',
                                                         'benchmark_score'],
              show_default=True, multiple=True)
@click.option('--sort', help='Sort by this column', default=['benchmark_score'], multiple=True, show_default=True)
def performance(prices, perf, cols, sort):
    df = get_performance(prices, perf)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df.sort_values(list(sort))[list(cols)].to_string(index=False))
