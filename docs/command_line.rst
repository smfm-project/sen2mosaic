
Using sen2mosaic on the command line
====================================

The most straightforward way of using sen2mosaic it to call its various stages from the Linux command line. Here I'll show how it can be used by example. Remember, each command line script has a help flag, which should be examined when in doubt.

Getting L1C data
----------------

For example, to download all data over tile 36KWA between for May and June 2017, with a maximum cloud cover percentage of 30 %, use the following command:

::
    python /path/to/sen2mosaic/L1C.py -u sam.bowers -p supersecret -t 36KWA -s 20170501 -e 20170630 -c 30


Processing to L2A
-----------------

For example, ...

Processing to L3A
-----------------

Processing to L3B
-----------------

The (unofficial) level 3B Sentintel-2 data product is a mosaic of multiple Sentinel-2 level 3A tiles in user-selected tiling grid. This script takes L3A data as input, selects the tiles that fall within the specified spatial extent, and mosaics available data into single-band GeoTiff files for easy use in classification systems.





