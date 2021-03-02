from __future__ import absolute_import
from datetime import datetime
from cloudperf.providers import aws_helpers

# static map until Amazon can provide the name in boto3 along with the region
# code...
region_map = {
    'Africa (Cape Town)': 'af-south-1',
    'Asia Pacific (Hong Kong)': 'ap-east-1',
    'Asia Pacific (KDDI) - Osaka': 'ap-northeast-1-wl1-kix1',
    'Asia Pacific (KDDI) - Tokyo': 'ap-northeast-1-wl1-nrt1',
    'Asia Pacific (Mumbai)': 'ap-south-1',
    'Asia Pacific (Osaka-Local)': 'ap-northeast-3',
    'Asia Pacific (Seoul)': 'ap-northeast-2',
    'Asia Pacific (Singapore)': 'ap-southeast-1',
    'Asia Pacific (SKT) - Daejeon': 'ap-northeast-2-wl1-cjj1',
    'Asia Pacific (Sydney)': 'ap-southeast-2',
    'Asia Pacific (Tokyo)': 'ap-northeast-1',
    'AWS GovCloud (US-East)': 'us-gov-east-1',
    'AWS GovCloud (US-West)': 'us-gov-west-1',
    'AWS GovCloud (US)': 'us-gov-west-1',
    'Canada (Central)': 'ca-central-1',
    'EU (Frankfurt)': 'eu-central-1',
    'EU (Ireland)': 'eu-west-1',
    'EU (London)': 'eu-west-2',
    'EU (Milan)': 'eu-south-1',
    'EU (Paris)': 'eu-west-3',
    'EU (Stockholm)': 'eu-north-1',
    'Middle East (Bahrain)': 'me-south-1',
    'South America (Sao Paulo)': 'sa-east-1',
    'US East (Boston)': 'us-east-1-iah-1',
    'US East (Houston)': 'us-east-1-iah-1',
    'US East (Miami)': 'us-east-1-mia-1',
    'US East (N. Virginia)': 'us-east-1',
    'US East (Ohio)': 'us-east-2',
    'US East (Verizon) - Atlanta': 'us-east-1-wl1-atl1',
    'US East (Verizon) - Boston': 'us-east-1-wl1',
    'US East (Verizon) - Dallas': 'us-east-1-wl1-dfw1',
    'US East (Verizon) - Miami': 'us-east-1-wl1-mia1',
    'US East (Verizon) - New York': 'us-east-1-wl1-nyc1',
    'US East (Verizon) - Washington DC': 'us-east-1-wl1-was1',
    'US West (Los Angeles)': 'us-west-2-lax-1',
    'US West (N. California)': 'us-west-1',
    'US West (Oregon)': 'us-west-2',
    'US West (Verizon) - Denver': 'us-west-2-wl1-den1',
    'US West (Verizon) - Las Vegas': 'us-west-2-wl1-las1',
    'US West (Verizon) - San Francisco Bay Area': 'us-west-2-wl1',
    'US West (Verizon) - Seattle': 'us-west-2-wl1-sea1',
}

location_map = {v: k for k, v in region_map.items()}


class CloudProvider(object):
    provider = 'aws'
    filters = {'operatingSystem': 'Linux', 'preInstalledSw': 'NA',
               'licenseModel': 'No License required', 'capacitystatus': 'Used',
               'tenancy': 'Shared'
               }

    def get_prices(self, fail_on_missing_regions=False, **filters):
        if not filters:
            filters = self.filters
        instances = aws_helpers.get_ec2_prices(fail_on_missing_regions=fail_on_missing_regions, **filters)
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
