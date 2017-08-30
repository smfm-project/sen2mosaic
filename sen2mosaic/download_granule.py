import argparse
import os
import datetime
import time
import pandas
import re
import sentinelsat


def download_granule(username, password, tile, start = '20161206', end = datetime.datetime.today().strftime('%Y%m%d'),  output = os.getcwd(), maxcloud = 100):
    '''
    Downloads all images from a single Sentinel-2 Granule that meet specified conditions.
    '''

    # Validate tile input format for search
    assert bool(re.match("[0-9]{2}[A-Z]{3}$",tile)), "The tile name input (%s) does not match the format ##XXX (e.g. 36KWA)."%tile

    # Set up sentinelsat API
    api = sentinelsat.SentinelAPI(username, password, 'https://scihub.copernicus.eu/dhus')

    startdate = sentinelsat.format_query_date(start)
    enddate = sentinelsat.format_query_date(end)

    # Search data, filtering by options.
    products = api.query(beginposition = (startdate,enddate),
                         platformname = 'Sentinel-2',
                         cloudcoverpercentage = (0,maxcloud),
                         filename = '*T%s*'%tile)

    # convert to Pandas DataFrame (for later tweaking of which files to download)
    products_df = api.to_dataframe(products)

    # And download
    api.download_all(products_df['uuid'], output)


if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Download Sentinel-2 data from the Sentinel Scientific Data Hub, specifying a particular tile, date ranges and degrees of cloud cover.')

    # Required arguments
    parser.add_argument('-u', '--user', type = str, help = "Sentinel data hub user name")
    parser.add_argument('-p', '--password', type = str, help = "Sentinel data hub password")
    parser.add_argument('-t', '--tile', type = str, help = "Sentinel 2 tile name, in format ##XXX")
    
    # Optional arguments
    parser.add_argument('-s', '--start', type = str, default = '20161206', help = "Start date for search in format YYYYMMDD. Start date may not precede 20161206, the date where the format of Sentinel-2 files were simplified. Defaults to 20161206.")
    parser.add_argument('-e', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for search in format YYYYMMDD. Defaults to today's date.")
    parser.add_argument('-c', '--cloud', type = int, default = 100, help = "Maximum percentage of cloud cover to download.")
    parser.add_argument('-o', '--output', type = str, default = os.getcwd(), help = "Optionally specify an output directory. Defaults to the present working directory.")

    # Get arguments
    args = parser.parse_args()
        
    # Run the script
    download_granule(args.user, args.password, args.tile, args.start, args.end, output = args.output, maxcloud = args.cloud)