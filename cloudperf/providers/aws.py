from __future__ import absolute_import
from datetime import datetime
from cloudperf.providers import aws_helpers

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

    def get_performance(self, prices_df, perf_df=None, update=None, expire=None, tags=[], **filters):
        if not filters:
            filters = self.filters
        # only pass our records
        prices_df = prices_df[prices_df['provider'] == self.provider]
        if perf_df is not None:
            perf_df = perf_df[perf_df['provider'] == self.provider]
        instances = aws_helpers.get_ec2_performance(prices_df, perf_df, update, expire, tags, **filters)
        if instances.empty:
            return instances
        # add a provider column
        instances['provider'] = self.provider

        return instances

    def terminate_instances(self):
        aws_helpers.terminate_instances()
