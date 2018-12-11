from __future__ import absolute_import
import pkgutil
import cloudperf.providers
import cachetools
import pandas as pd


@cachetools.cached(cache={})
def get_providers():
    prov_path = cloudperf.providers.__path__
    providers = []
    for importer, name, ispkg in pkgutil.iter_modules(prov_path):
        m = importer.find_module(name).load_module('{}.{}'.format(prov_path, name))
        if getattr(m, 'CloudProvider', None):
            providers.append(m.CloudProvider())
    return providers


@cachetools.cached(cache={})
def get_prices(prices=None):
    if not prices:
        return (pd.concat([cp.get_prices() for cp in get_providers()], ignore_index=True, sort=False))
    return pd.read_json(prices, orient='records')


def get_performance(prices=None, perf=None):
    price_df = get_prices(prices)

    if not perf:
        return (pd.concat([cp.get_performance() for cp in get_providers()], ignore_index=True, sort=False))
    return pd.read_json(perf, orient='records')
