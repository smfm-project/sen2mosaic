
Command line tools
==================

The most straightforward way of using sen2mosaic it to call its various stages from the Linux command line. Here the functionality of each of the four commands is explained. In the next section we show how it can be used by example.

.. note:: Remember, each command line script has a help flag, which can be examined when in doubt.

Getting L1C data
----------------

Data from Sentinel-2 are available from the `Copernicus Open Access Data Hub <https://scihub.copernicus.eu/>`_, which has a graphical interface to download scenes from selected areas. Whilst useful for smaller areas, generating mosaics at national scales requires a volume of data which makes this extremely labour intensive.

The alternative is to download data using the `API Hub <https://scihub.copernicus.eu/twiki/do/view/SciHubWebPortal/APIHubDescription>`_. This system allows users to search for files using conditions on the command line, and automatically download files. To interface with the API hub, we use an excellent open source utility called `Sentinelsat <https://sentinelsat.readthedocs.io/en/v0.12/>`_. This operates both as a command line tool, and as a Python API, which we use here. You will need to sign up for an account at `Scihub <https://scihub.copernicus.eu/>`_.

``L1C.py`` is a program to interface with Sentinelsat to download Sentinel-2 files, specifying a particular tile, date ranges and degrees of cloud cover. It will also decompress and tidy up .zip files, ready for use with ``L2A.py``.

Help for ``L1C.py`` can be viewed by typing `python /path/to/sen2mosaic/L1C.py --help`_:

.. code-block:: console
    
    usage: L1C.py [-h] -u USER -p PASS -t TILE [-s START] [-e END] [-c CLOUD]
                [-o PATH] [-r]

    Download Sentinel-2 data from the Copernicus Open Access Hub, specifying a
    particular tile, date ranges and degrees of cloud cover.

    Required arguments:
    -u USER, --user USER  Scihub username
    -p PASS, --password PASS
                            Scihub password
    -t TILE, --tile TILE  Sentinel 2 tile name, in format ##XXX

    Optional arguments:
    -s START, --start START
                            Start date for search in format YYYYMMDD. Start date
                            may not precede 20161206, the date where the format of
                            Sentinel-2 files was simplified. Defaults to 20161206.
    -e END, --end END     End date for search in format YYYYMMDD. Defaults to
                            today's date.
    -c CLOUD, --cloud CLOUD
                            Maximum percentage of cloud cover to download.
                            Defaults to 100 % (download all images, regardless of
                            cloud cover).
    -o PATH, --output_dir PATH
                            Specify an output directory. Defaults to the present
                            working directory.
    -r, --remove          Optionally remove level 1C .zip files after
                            decompression.


For example, to download all data for tile 36KWA between for May and June 2017, with a maximum cloud cover percentage of 30 %, specifying an output location and removing decompressed .zip files, use the following command:

.. code-block:: console
    
    python /path/to/sen2mosaic/L1C.py -u user.name -p supersecret -t 36KWA -s 20170501 -e 20170630 -c 30 -r -o ~/path/to/36KWA_data/

.. note:: If you already have access to Sentinel-2 data, you can skip straight to L2A.py. This may be the case if you're using a cloud platform where Sentinel-2 data archives are stored at the same location as servers.

Processing to L2A
-----------------

Once you have Sentinel-2 (Level 1C) data, the next step is to perform atmospheric correction and identify clouds and cloud shadows. This step is based on `sen2cor <http://step.esa.int/main/third-party-plugins-2/sen2cor/>`_.

`L2A.py` takes a list of level 1C .SAFE files as input, initiates sen2cor, and performs simple modifications to improve the quality of it's cloud and cloud shadow mask.

Help for ``L2A.py`` can be viewed by typing `python /path/to/sen2mosaic/L2A.py --help`_:

usage: L2A.py [-h] [-g GIPP] [-o OUTPUT_DIR] [-r] N [N ...]

Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to bottom
of atmosphere reflectance, and generate a cloud mask. This script initiates
sen2cor, then performs simple improvements to the cloud mask.

.. code-block:: console
    
    usage: L2A.py [-h] [-g GIPP] [-o DIR] [-r] L1C_FILES [L1C_FILES ...]

    Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level
    2A. This script initiates sen2cor, which performs atmospheric correction and
    generate a cloud mask. This script also performs simple improvements to the
    cloud mask.

    Required arguments:
    L1C_FILES             Sentinel 2 input files (level 1C) in .SAFE format.
                            Specify one or more valid Sentinel-2 input files, or
                            multiple files through wildcards (e.g.
                            PATH/TO/*_MSIL1C_*.SAFE). Input files will be
                            atmospherically corrected.

    Optional arguments:
    -g GIPP, --gipp GIPP  Specify a custom L2A_Process settings file (default =
                            sen2cor/cfg/L2A_GIPP.xml). Required if specifying
                            output directory.
    -o DIR, --output_dir DIR
                            Specify a directory to output level 2A files. If not
                            specified, atmospherically corrected images will be
                            written to the same directory as input files.
    -r, --remove          Delete input level 1C files after processing.


For example, to run L2A.py on a set of level 1C Sentinel-2 files in a directory, use the following command:

.. code-block:: console
    
    python /path/to/sen2mosaic/L2A.py ~/path/to/36KWA_data/S2*_MSIL1C_*.SAFE

If specifying an output directory, you'll need to include a reference to the location of your sen2cor options file ('GIPP'). This is by default in the directory /path/to/sen2cor/cfg/L2A_GIPP.xml, but can be moved to a location of your choosing. To write outputs to the same directory as input files, and delete level 1C files after processing, input:

.. code-block:: console
    
    python /path/to/sen2mosaic/L2A.py -r -g /path/to/sen2mosaic/cfg/L2A_GIPP.xml -o /path/to/36KWA_data/ /path/to/36KWA_data/S2*_MSIL1C_*.SAFE

Processing to L3A
-----------------

The final data processing step is to combine cloud-masked images for each tile into a single cloud-free composite image. This step is based on `sen2three <http://step.esa.int/main/third-party-plugins-2/sen2three/>`_.

``L3A.py`` takes a directory containing level 2A .SAFE files as input, and initiates sen2three.

Help for ``L3A.py`` can be viewed by typing ``python /path/to/sen2mosaic/L3A.py --help``:

.. code-block:: console

    usage: L3A.py [-h] [-r] L2A_DIR

    Process level 2A Sentinel-2 data from sen2cor to cloud free mosaics with
    sen2three. This script initiates sen2three from Python. It also tidies up the
    large database files left behind by sen2three. Level 3A files will be output
    to the same directory as input files.

    Required arguments:
    L2A_DIR       Directory where the Level-2A input files are located (e.g.
                    PATH/TO/L2A_DIRECTORY/) By default this will be the current
                    working directory.

    Optional arguments:
    -r, --remove  Optionally remove all matching Sentinel-2 level 2A files from
                    input directory. Be careful.


For example, to run L3A.py on the directory ``/path/to/36KWA_data/`` which contains L2A data for the tile 36KWA and output the level 3A product to the same directory, use the following command:

.. code-block:: console
    
    python /path/to/sen2mosaic/L3A.py -o /path/to/36KWA_data/ /path/to/36KWA_data/
    
    
Processing to L3B
-----------------

The (unofficial) level 3B Sentintel-2 data product is a mosaic of multiple Sentinel-2 level 3A tiles in user-specified tiling grid. This script takes L3A data as input, selects the tiles that fall within the specified spatial extent, and mosaics available data into single-band GeoTiff files for easy use in classification systems.

``L3B.py`` takes a directory containing level 3A .SAFE files, an output image extent (xmin, ymin, xmax, ymax) and projection EPSG code as input.

Help for ``L3B.py`` can be viewed by typing ``python /path/to/sen2mosaic/L3B.py --help``:

.. code-block:: console

    usage: L3B.py [-h] [-te XMIN YMIN XMAX YMAX] [-e EPSG] [-o DIR] [-n NAME]
                L3A_FILES [L3A_FILES ...]

    Process Sentinel-2 level 3A data to unofficial 'level 3B'. This script mosaics
    L3A into a customisable grid square, based on specified UTM coordinate bounds.
    Files are output as GeoTiffs, which are easier to work with than JPEG2000
    files.

    required arguments:
    L3A_FILES             Sentinel-2 level 3A input files in .SAFE format.
                            Specify a valid S2 input file or multiple files
                            through wildcards (e.g. PATH/TO/*_MSIL3A_*.SAFE).
    -te XMIN YMIN XMAX YMAX, --target_extent XMIN YMIN XMAX YMAX
                            Extent of output image tile, in format <xmin, ymin,
                            xmax, ymax>.
    -e EPSG, --epsg EPSG  EPSG code for output image tile CRS. This must be UTM.
                            Find the EPSG code of your output CRS as https://www
                            .epsg-registry.org/.

    optional arguments:
    -o DIR, --output_dir DIR
                            Optionally specify an output directory. If nothing
                            specified, downloads will output to the present
                            working directory, given a standard filename.
    -n NAME, --output_name NAME
                            Optionally specify a string to precede output
                            filename.


For example, to run L3B.py in the directory ``/path/to/L3A_tiles/`` which contains level 3A files to create a 200 x 200 km output tile in the UTM36S projection, input:

.. code-block:: console
    
    python /path/to/sen2mosaic/L3B.py -te 700000 7900000 900000 8100000 -e 32736 /path/to/L3A_tiles/S2A_MSIL03_*.SAFE

To do the same operation, but specifying an output directory and a name to prepend to outputs from this tile, input:

.. code-block:: console
    
    python /path/to/sen2mosaic/L3B.py -te 700000 7900000 900000 8100000 -e 32736 -o /path/to/output/ -n tile_1 /path/to/L3A_tiles/S2A_MSIL03_*.SAFE





