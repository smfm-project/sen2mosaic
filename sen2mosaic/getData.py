import argparse
import os
import datetime
import time
import pandas
import re
import sentinelsat


def connectToAPI(username, password):
    '''
    Connect to the SciHub API with sentinelsat.
    '''
    
    # Let API be accessed by other functions
    global scihub_api
    
    # Connect to Sentinel API
    scihub_api = sentinelsat.SentinelAPI(username, password, 'https://scihub.copernicus.eu/dhus')
    


def search(tile, start = '20161206', end = datetime.datetime.today().strftime('%Y%m%d'),  maxcloud = 100):
    '''
    Searches for images from a single Sentinel-2 Granule that meet conditions of date range and cloud cover.
    Returns a dataframe with details of scenes matching conditions.
    '''

    # Test that we're connected to the 
    assert 'scihub_api' in globals(), "The global variable scihub_api doesn't exist. You should run connectToAPI(username, password) before searching the data archive."

    # Validate tile input format for search
    assert bool(re.match("[0-9]{2}[A-Z]{3}$",tile)), "The tile name input (%s) does not match the format ##XXX (e.g. 36KWA)."%tile

    # Set up start and end dates
    startdate = sentinelsat.format_query_date(start)
    enddate = sentinelsat.format_query_date(end)

    # Search data, filtering by options.
    products = scihub_api.query(beginposition = (startdate,enddate),
                         platformname = 'Sentinel-2',
                         cloudcoverpercentage = (0,maxcloud),
                         filename = '*T%s*'%tile)

    # convert to Pandas DataFrame, which can be searched modified before commiting to download()
    products_df = scihub_api.to_dataframe(products)

    return products_df


def download(products_df, output = os.getcwd()):
    '''
    Downloads all images from a dataframe produced by sentinelsat.
    '''
    
    # And download selected products
    scihub_api.download_all(products_df['uuid'], output)



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
    
    # Connect to API
    connectToAPI(args.user, args.password)
        
    # Search for files, return a data frame
    products = search(args.tile, start = args.start, end = args.end, maxcloud = args.cloud)
    
    # Download products
    download(products, output = args.output)
    
