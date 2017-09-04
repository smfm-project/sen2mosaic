import argparse
import datetime
import glob
import os
import pandas
import re
import time
import sentinelsat
import zipfile

"""
A set of tools to assist in the searching, downloading, and decompression of Sentinel-2 data that matches critera of acquisition date and cloud cover for a given Sentinel-2 tile.
"""


def connectToAPI(username, password):
    '''
    Connect to the SciHub API with sentinelsat.
    '''
    
    # Let API be accessed by other functions
    global scihub_api
    
    # Connect to Sentinel API
    scihub_api = sentinelsat.SentinelAPI(username, password, 'https://scihub.copernicus.eu/dhus')
    

def validateTile(tile):
    '''
    Validates the name structure of a Sentinel-2 tile
    '''
    
    # Tests whether string is in format ##XXX
    name_test = re.match("[0-9]{2}[A-Z]{3}$",tile)
    
    return bool(name_test)
    

def search(tile, start = '20161206', end = datetime.datetime.today().strftime('%Y%m%d'),  maxcloud = 100):
    '''
    Searches for images from a single Sentinel-2 Granule that meet conditions of date range and cloud cover.
    Returns a dataframe with details of scenes matching conditions.
    '''

    # Test that we're connected to the 
    assert 'scihub_api' in globals(), "The global variable scihub_api doesn't exist. You should run connectToAPI(username, password) before searching the data archive."

    # Validate tile input format for search
    assert validateTile(tile), "The tile name input (%s) does not match the format ##XXX (e.g. 36KWA)."%tile

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


def download(products_df, output_dir = os.getcwd()):
    '''
    Downloads all images from a dataframe produced by sentinelsat.
    '''

    if products_df.empty == True:
        print 'WARNING: No products found to download. Check your search terms.'
        
    else:
        # Download selected products
        scihub_api.download_all(products_df['uuid'], output_dir)


def decompress(tile, dataloc = os.getcwd()):
    '''
    Unzips .zip files downloaded from SciHub
    '''

    # Validate tile input format for file search
    assert validateTile(tile), "The tile name input (%s) does not match the format ##XXX (e.g. 36KWA)."%tile
    
    # Remove trailing slash to directory name where included
    dataloc = dataloc.rstrip('/')
    
    # Get a list of zip files matching the Level 1C file pattern
    zip_files = glob.glob('%s/*_MSIL1C_*_T%s_*.zip'%(dataloc,tile))
    
    # Unzip each one using the system command
    for zip_file in zip_files:
        print 'Extracting %s'%zip_file
        obj = zipfile.ZipFile(zip_file)
        obj.extractall(dataloc)


def main(username, password, tile, start = '20161206', end = datetime.datetime.today().strftime('%Y%m%d'), maxcloud = 100, output_dir = os.getcwd()):
    '''
    Function to initiate entire data preparation sequence.
    '''
    
    # Connect to API
    connectToAPI(username, password)
        
    # Search for files, return a data frame containing details of matching Sentinel-2 images
    products = search(tile, start = args.start, end = args.end, maxcloud = args.cloud)

    # Download products
    download(products, output_dir = output_dir)
    
    # Decompress data
    decompress(args.tile, dataloc = output_dir)
    


if __name__ == '__main__':

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Download Sentinel-2 data from the Copernicus Open Access Hub, specifying a particular tile, date ranges and degrees of cloud cover.')

    # Required arguments
    parser.add_argument('-u', '--user', type = str, help = "Scihub username")
    parser.add_argument('-p', '--password', type = str, help = "Scihub password")
    parser.add_argument('-t', '--tile', type = str, help = "Sentinel 2 tile name, in format ##XXX")
    
    # Optional arguments
    parser.add_argument('-s', '--start', type = str, default = '20161206', help = "Start date for search in format YYYYMMDD. Start date may not precede 20161206, the date where the format of Sentinel-2 files was simplified. Defaults to 20161206.")
    parser.add_argument('-e', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for search in format YYYYMMDD. Defaults to today's date.")
    parser.add_argument('-c', '--cloud', type = int, default = 100, help = "Maximum percentage of cloud cover to download.")
    parser.add_argument('-o', '--output_dir', type = str, default = os.getcwd(), help = "Optionally specify an output directory. Defaults to the present working directory.")

    # Get arguments from command line
    args = parser.parse_args()
    
    # Run through entire processing sequence
    main(args.user, args.password, args.tile, start = args.start, end = args.end, maxcloud = args.cloud, output_dir = args.output_dir)
