from __future__ import absolute_import
from datetime import datetime
from cloudperf.providers import aws_helpers


class CloudProvider(object):
    provider = 'aws'
    filters = {'operatingSystem': 'Linux', 'preInstalledSw': 'NA',
               'licenseModel': 'No License required', 'capacitystatus': 'Used',
               'tenancy': 'Shared',
               #'instanceType':'c5.2xlarge'
               }

    def get_prices(self, **filters):
        if not filters:
            filters = self.filters
        instances = aws_helpers.get_ec2_prices(**filters)
        # place the current time as a timestamp
        instances['updated_at'] = datetime.now()
        # add a provider column
        instances['provider'] = self.provider

        return instances

    def get_performance(self, prices_df, **filters):
        if not filters:
            filters = self.filters
        instances = aws_helpers.get_ec2_performance(prices_df, **filters)
        # place the current time as a timestamp
        instances['updated_at'] = datetime.now()
        # add a provider column
        instances['provider'] = self.provider

        return instances
