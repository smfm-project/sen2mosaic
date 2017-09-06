
Using sen2mosaic on the command line
====================================

The most straightforward way of using sen2mosaic it to call its various stages from the Linux command line. Here I'll show how it can be used by example. Remember, each command line script has a help flag, which can be examined when in doubt.

Getting L1C data
----------------

Data from Sentinel-2 are available from the [Copernicus Open Access Data Hub](https://scihub.copernicus.eu/), which has a graphical interface to download scenes from selected areas. Whilst useful for smaller areas, generating mosaics at national scales requires a volume of data which makes this extremely labour intensive.

The alternative is to download data using the '[API Hub](https://scihub.copernicus.eu/twiki/do/view/SciHubWebPortal/APIHubDescription)'. This system allows users to search for files using conditions on the command line, and automatically download files. To interface with the API hub, we use an excellent open source utility called [Sentinelsat](https://sentinelsat.readthedocs.io/en/v0.12/). This operates both as a command line tool, and as a Python API, which we use here. You will need to sign up at [Scihub](https://scihub.copernicus.eu/)

L1C.py is a program to interface with Sentinelsat to download Sentinel-2 files, specifying a particular tile, date ranges and degrees of cloud cover. It will also decompress and tidy up .zip files, ready for use with L2A.py.

For example, to download all data for tile 36KWA between for May and June 2017, with a maximum cloud cover percentage of 30 %, removing decompressed .zip files and specifying an output location, use the following command:

::
    python /path/to/sen2mosaic/L1C.py -u sam.bowers -p supersecret -t 36KWA -s 20170501 -e 20170630 -c 30 -r -o ~/path/to/output/

{info:title=If you already have access to Sentinel-2 data...}Skip to L2A.py. This may be the case if you're using a cloud platform where Sentinel-2 data archives are stored at the same location as servers.{info}

Processing to L2A
-----------------

Once you have Sentinel-2 (Level 1C) data, the next step is to perform atmospheric correction and identify clouds and cloud shadows. This step is based on [sen2cor](http://step.esa.int/main/third-party-plugins-2/sen2cor/). 

L2A.py takes a list of level 1C .SAFE files as input, initiates sen2cor, and performs simple modifications to improve the quality of it's cloud and cloud shasdow mask.

If specifying an output directory, you'll need to include a reference to the location of your sen2cor options file ('GIPP'). This is by default in the directory /path/to/sen2cor/cfg/L2A_GIPP.xml, which should be copied to a location of your choosing.

For example, to run L2A.py on a set of level 1C Sentinel-2 files in a directory, use the following command:

::
    python /path/to/sen2mosaic/L2A.py /path/to/input/S2*_MSIL1C_*.SAFE

To specify an output directory, and delete level 1C files after processing, input:

::
    python /path/to/sen2mosaic/L2A.py -r -g /path/to/sen2mosaic/cfg/L2A_GIPP.xml -o /path/to/input/ /path/to/input/S2*_MSIL1C_*.SAFE

Processing to L3A
-----------------

Processing to L3B
-----------------

The (unofficial) level 3B Sentintel-2 data product is a mosaic of multiple Sentinel-2 level 3A tiles in user-selected tiling grid. This script takes L3A data as input, selects the tiles that fall within the specified spatial extent, and mosaics available data into single-band GeoTiff files for easy use in classification systems.





