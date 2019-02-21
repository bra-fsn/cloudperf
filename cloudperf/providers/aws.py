from __future__ import absolute_import
from datetime import datetime
from cloudperf.providers import aws_helpers


class CloudProvider(object):
    provider = 'aws'
    filters = {'operatingSystem': 'Linux', 'preInstalledSw': 'NA',
               'licenseModel': 'No License required', 'capacitystatus': 'Used',
               'tenancy': 'Shared'
               }

    def get_prices(self, **filters):
        if not filters:
            filters = self.filters
        instances = aws_helpers.get_ec2_prices(**filters)
        # add a provider column
        instances['provider'] = self.provider

        return instances

    def get_performance(self, prices_df, perf_df=None, update=None, expire=None, **filters):
        if not filters:
            filters = self.filters
        # only pass our records
        prices_df = prices_df[prices_df['provider'] == self.provider]
        if perf_df is not None:
            perf_df = perf_df[perf_df['provider'] == self.provider]
        instances = aws_helpers.get_ec2_performance(prices_df, perf_df, update, expire, **filters)
        # add a provider column
        instances['provider'] = self.provider

        return instances

    def terminate_instances(self):
        aws_helpers.terminate_instances()
