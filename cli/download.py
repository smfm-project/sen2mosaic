#!/usr/bin/env python

import argparse
import datetime
import os

import sen2mosaic.download

import pdb

##############################################################
### Command line interface for downloading Sentinel-2 data ###
##############################################################

def main(username, password, tiles, level = '1C', start = '20150523', end = datetime.datetime.today().strftime('%Y%m%d'), maxcloud = 100, minsize = 25., output_dir = os.getcwd(), remove = False):
    """main(username, password, tiles, level = '1C', start = '20150523', end = datetime.datetime.today().strftime('%Y%m%d'), maxcloud = 100, minsize = 25., output_dir = os.getcwd(), remove = False)
    
    Download Sentinel-2 data from the Copernicus Open Access Hub, specifying a particular tile, date ranges and degrees of cloud cover. This is the function that is initiated from the command line.
    
    Args:
        username: Scihub username. Sign up at https://scihub.copernicus.eu/.
        password: Scihub password.
        tiles: A string containing the name of the tile to to download, or a list of tiles.
        level: Download level '1C' (default) or '2A' data.
        start: Start date for search in format YYYYMMDD. Defaults to '20150523'.
        end: End date for search in format YYYYMMDD. Defaults to today's date.
        maxcloud: An integer of maximum percentage of cloud cover to download. Defaults to 100 %% (download all images, regardless of cloud cover).
        minsize: A float with the minimum filesize to download in MB. Defaults to 25 MB.  Be aware, file sizes smaller than this can result sen2three crashing.
        output_dir: Optionally specify an output directory. Defaults to the present working directory.
        remove: Boolean value, which when set to True deletes level 1C .zip files after decompression is complete. Defaults to False.
    """
    
    # Allow download of single tile
    if type(tiles) == str: tiles = [tiles]
    
    for tile in tiles:
                
        # Connect to API (or reconnect, after timeout)
        sen2mosaic.download.connectToAPI(username, password)
    
        # Search for files, return a data frame containing details of matching Sentinel-2 images
        products = sen2mosaic.download.search(tile, level = level, start = start, end = end, maxcloud = maxcloud, minsize = minsize)
        
        # Where no data
        if len(products) == 0: continue
        
        # Download products
        zip_files = sen2mosaic.download.download(products, output_dir = output_dir)
        
        # Decompress data
        sen2mosaic.download.decompress(zip_files, output_dir = output_dir, remove = remove)
        


if __name__ == '__main__':
    '''
    '''

    # Set up command line parser
    parser = argparse.ArgumentParser(description = 'Download Sentinel-2 data from the Copernicus Open Access Hub, specifying a particular tile, date ranges and degrees of cloud cover.')

    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # Required arguments
    required.add_argument('-u', '--user', type = str, required = True, help = "Scihub username")
    required.add_argument('-p', '--password', type = str, metavar = 'PASS', required = True, help = "Scihub password")
    required.add_argument('-t', '--tiles', type = str, required = True, nargs = '*', help = "Sentinel 2 tile name, in format ##XXX")
    
    # Optional arguments
    optional.add_argument('-l', '--level', type = str, default = '1C', help = "Set to search and download level '1C' (default) or '2A' data. Note that L2A data may not be available at all locations.")
    optional.add_argument('-s', '--start', type = str, default = '20150523', help = "Start date for search in format YYYYMMDD. Defaults to 20150523.")
    optional.add_argument('-e', '--end', type = str, default = datetime.datetime.today().strftime('%Y%m%d'), help = "End date for search in format YYYYMMDD. Defaults to today's date.")
    optional.add_argument('-c', '--cloud', type = int, default = 100, metavar = '%', help = "Maximum percentage of cloud cover to download. Defaults to 100 %% (download all images, regardless of cloud cover).")
    optional.add_argument('-m', '--minsize', type = int, default = 25., metavar = 'MB', help = "Minimum file size to download in MB. Defaults to 25 MB.")
    optional.add_argument('-o', '--output_dir', type = str, metavar = 'PATH', default = os.getcwd(), help = "Specify an output directory. Defaults to the present working directory.")
    optional.add_argument('-r', '--remove', action='store_true', default = False, help = "Remove level 1C .zip files after decompression.")
        
    # Get arguments from command line
    args = parser.parse_args()
    
    # Run through entire processing sequence
    main(args.user, args.password, args.tiles, level = args.level, start = args.start, end = args.end, maxcloud = args.cloud, minsize = args.minsize, output_dir = args.output_dir, remove = args.remove)
