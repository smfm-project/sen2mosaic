
Command line tools
==================

The most straightforward way of using sen2mosaic it to call its various stages from the Linux command line. Here the functionality of each of the four commands is explained. In the next section we show how it can be used by example.

.. note:: Remember, each command line script has a help flag, which can be examined when in doubt.

Getting L1C data
----------------

Data from Sentinel-2 are available from the `Copernicus Open Access Data Hub <https://scihub.copernicus.eu/>`_, which has a graphical interface to download scenes from selected areas. Whilst useful for smaller areas, generating mosaics at national scales requires a volume of data which makes this extremely labour intensive.

.. note:: If you already have access to Sentinel-2 data, you can skip straight to ``preprocess.py``. This may be the case if you're using a cloud platform where Sentinel-2 data archives are stored at the same location as servers.

The alternative is to download data using the `API Hub <https://scihub.copernicus.eu/twiki/do/view/SciHubWebPortal/APIHubDescription>`_. This system allows users to search for files using conditions on the command line, and automatically download files. To interface with the API hub, we use an excellent open source utility called `Sentinelsat <https://sentinelsat.readthedocs.io/en/v0.12/>`_. This operates both as a command line tool, and as a Python API, which we use here. You will need to sign up for an account at `Scihub <https://scihub.copernicus.eu/>`_.

``download.py`` is a program to interface with Sentinelsat to download Sentinel-2 files, specifying a particular tile, date ranges and degrees of cloud cover. It will also decompress and tidy up .zip files, ready for use with ``preprocess.py``.

Help for ``download.py`` can be viewed by typing ``s2m download --help``:

.. code-block:: console
    
    usage: download.py [-h] -u USER -p PASS -t [TILES [TILES ...]] [-l LEVEL]
                    [-s START] [-e END] [-c %] [-m MB] [-o PATH] [-r]

    Download Sentinel-2 data from the Copernicus Open Access Hub, specifying a
    particular tile, date ranges and degrees of cloud cover.

    Required arguments:
    -u USER, --user USER  Scihub username
    -p PASS, --password PASS
                            Scihub password
    -t [TILES [TILES ...]], --tiles [TILES [TILES ...]]
                            Sentinel 2 tile name, in format ##XXX

    Optional arguments:
    -l LEVEL, --level LEVEL
                            Set to search and download level '1C' (default) or
                            '2A' data. Note that L2A data may not be available at
                            all locations.
    -s START, --start START
                            Start date for search in format YYYYMMDD. Defaults to
                            20150523.
    -e END, --end END     End date for search in format YYYYMMDD. Defaults to
                            today's date.
    -c %, --cloud %       Maximum percentage of cloud cover to download.
                            Defaults to 100 % (download all images, regardless of
                            cloud cover).
    -m MB, --minsize MB   Minimum file size to download in MB. Defaults to 25
                            MB.
    -o PATH, --output_dir PATH
                            Specify an output directory. Defaults to the present
                            working directory.
    -r, --remove          Remove level 1C .zip files after decompression.


For example, to download all data for tile 36KWA between for May and June 2017, with a maximum cloud cover percentage of 30 %, specifying an output location and removing decompressed .zip files, use the following command:

.. code-block:: console
    
    s2m download -u user.name -p supersecret -t 36KWA -s 20170501 -e 20170630 -c 30 -r -o /path/to/DATA_dir/

.. note:: **What if I want data before 6th December 2016?**. 
   
    The format in which Sentinel-2 data is distributed was modified in December 2016, and the earlier format is not well supported. As there is a limited volume of data from before this date, we recommend downloading the data from `Scihub <https://scihub.copernicus.eu/>`_.
    
    A nice tool to help out with this is `aria2 <https://aria2.github.io/>`_. After adding products to your basket at Sentinelhub, you'll download a metadata file called ``products.meta4``. Use aria2 to download the file's contents as follows:
    
    .. code-block:: console
        
        aria2c --http-user=username --http-passwd=supersecret --check-certificate=false --max-concurrent-downloads=2 -M products.meta4

Processing to L2A
-----------------

Once you have Sentinel-2 (Level 1C) data, the next step is to perform atmospheric correction and identify clouds and cloud shadows. This step is based on `sen2cor <http://step.esa.int/main/third-party-plugins-2/sen2cor/>`_.

.. note:: If you already have access to Sentinel-2 L2A, skip straight to ``mosaic.py``. This may be the case if you're using a cloud platform where Sentinel-2 data archives are stored at the same location as servers. You can also skip this step if you're happy to build a mosaic using L1C data, but be aware that the output will be of lower quality.

``preprocess.py`` takes a list of level 1C .SAFE files as input, initiates sen2cor, and performs simple modifications to improve the quality of it's cloud and cloud shadow mask.

Help for ``preprocess.py`` can be viewed by typing ``s2m preprocess --help``:

.. code-block:: console
    
    usage: preprocess.py [-h] [-t TILE] [-g GIPP] [-o DIR] [-res 10/20/60]
                        [-s PATH] [-s255 PATH] [-p N] [-v]
                        [L1C_FILES [L1C_FILES ...]]

    Process level 1C Sentinel-2 data from the Copernicus Open Access Hub to level
    2A. This script initiates sen2cor, which performs atmospheric correction and
    generate a cloud mask. This script also performs simple improvements to the
    cloud mask.

    Positional arguments:
    L1C_FILES             Sentinel 2 input files (level 1C) in .SAFE format.
                            Specify one or more valid Sentinel-2 .SAFE, a
                            directory containing .SAFE files, a Sentinel-2 tile or
                            multiple granules through wildcards (e.g.
                            *.SAFE/GRANULE/*), or a file containing a list of
                            input files. Leave blank to process files in current
                            working directoy. All granules that match input
                            conditions will be atmospherically corrected.

    Optional arguments:
    -t TILE, --tile TILE  Specify a specific Sentinel-2 tile to process. If
                            omitted, all tiles in L1C_FILES will be processed.
    -g GIPP, --gipp GIPP  optionally specify a custom L2A_Process settings file.
    -o DIR, --output_dir DIR
                            Specify a directory to output level 2A files. If not
                            specified, atmospherically corrected images will be
                            written to the same directory as input files.
    -res 10/20/60, --resolution 10/20/60
                            Process only one of the Sentinel-2 resolutions, with
                            options of 10, 20, or 60 m. Defaults to processing all
                            three. N.B It is not currently possible to only the 10
                            m resolution, an input of 10 m will instead process
                            all resolutions.
    -s PATH, --sen2cor PATH
                            Path to sen2cor (v2.8), if not callable with the
                            default 'L2A_Process'.
    -s255 PATH, --sen2cor255 PATH
                            Path to sen2cor (v2.5.5), required if processing
                            Sentinel-2 data with the old file format.
    -p N, --n_processes N
                            Specify a maximum number of tiles to process in
                            paralell. Bear in mind that more processes will
                            require more memory. Defaults to 1.
    -v, --verbose         Make script verbose.

For example, to run ``preprocess.py`` on a set of level 1C Sentinel-2 files in a directory, processing only 20 m resolution data, use the following command:

.. code-block:: console
    
    s2m preprocess -res 20 /path/to/DATA_dir/

The pre-processing script supports parallel processing of L1C files. Be aware that this will entail greater processing and memory requirements than are available on most standard desktop PCs. To parallel process 3 tiles for the 20 m resolution, input:

.. code-block:: console
    
    s2m preprocess -res 20 -n 3 /path/to/DATA_dir/
    
Processing to a mosaic
----------------------

The final ``sen2mosaic`` processing step creates a composite image of multiple Sentinel-2 level 2A images in user-specified tiling grid. This script takes L2A data as input, identifies the tiles that fall within the specified spatial extent, and builds a composite image using available data to produce single-band GeoTiff files for easy use in classification systems.

.. note:: You can also build a mosaic using L1C data, but be aware that the output will be of lower quality.

``mosaic.py`` takes a directory containing Sentinel-2 .SAFE files, an output image extent (xmin, ymin, xmax, ymax) and projection EPSG code as inputs, along with a series of options to modify the compositing approach.

Help for ``mosaic.py`` can be viewed by typing ``s2m mosaic --help``:

.. code-block:: console
    
    usage: mosaic.py [-h] -te XMIN YMIN XMAX YMAX -e EPSG [-res m] [-l 1C/2A]
                    [-st START] [-en END] [-pc PC] [-m [N [N ...]]] [-b] [-i]
                    [-t DIR] [-o DIR] [-n NAME] [-p N] [-v]
                    [PATH [PATH ...]]

    Process Sentinel-2 data to a composite mosaic product to a customisable grid
    square, based on specified UTM coordinate bounds. Data are output as GeoTiff
    files for each spectral band, with .vrt files for ease of visualisation.

    positional arguments:
    PATH                  Sentinel 2 input files (level 1C/2A) in .SAFE format.
                            Specify one or more valid Sentinel-2 .SAFE, a
                            directory containing .SAFE files, a Sentinel-2 tile or
                            multiple granules through wildcards (e.g.
                            *.SAFE/GRANULE/*), or a file containing a list of
                            input files. Leave blank to process files in current
                            working directoy. All granules that match input
                            conditions will be included.

    required arguments:
    -te XMIN YMIN XMAX YMAX, --target_extent XMIN YMIN XMAX YMAX
                            Extent of output image tile, in format <xmin, ymin,
                            xmax, ymax>.
    -e EPSG, --epsg EPSG  EPSG code for output image tile CRS. This must be UTM.
                            Find the EPSG code of your output CRS as
                            https://www.epsg-registry.org/.
    -res m, --resolution m
                            Specify a resolution in metres.

    optional arguments:
    -l 1C/2A, --level 1C/2A
                            Input image processing level, '1C' or '2A'. Defaults
                            to '2A'.
    -st START, --start START
                            Start date for tiles to include in format YYYYMMDD.
                            Defaults to processing all dates.
    -en END, --end END    End date for tiles to include in format YYYYMMDD.
                            Defaults to processing all dates.
    -pc PC, --percentile PC
                            Specify a percentile of reflectance to output.
                            Defaults to 25 percent, which tends to produce good
                            results.
    -m [N [N ...]], --masked_vals [N [N ...]]
                            Specify SLC values to not include in the mosaic (e.g.
                            -m 7 8 9). See http://step.esa.int/main/third-party-
                            plugins-2/sen2cor/ for description of sen2cor mask
                            values. Defaults to 'auto', which masks values 0 and
                            9. Also accepts 'none', to include all values.
    -b, --colour_balance  Perform colour balancing between tiles. Not generally
                            recommended, particularly where working over large
                            areas. Defaults to False.
    -i, --improve_mask    Apply improvements to Sentinel-2 cloud mask. Not
                            generally recommended, except where a very
                            conservative mask is desired. Defaults to no
                            improvement.
    -t DIR, --temp_dir DIR
                            Directory to write temporary files, only required for
                            L1C data. Defaults to '/tmp'.
    -o DIR, --output_dir DIR
                            Specify an output directory. Defaults to the present
                            working directory.
    -n NAME, --output_name NAME
                            Specify a string to precede output filename. Defaults
                            to 'mosaic'.
    -p N, --n_processes N
                            Specify a maximum number of tiles to process in
                            paralell. Bear in mind that more processes will
                            require more memory. Defaults to 1.
    -v, --verbose         Make script verbose.
    
For example, to run ``mosaic.py`` in the directory ``/path/to/DATA_dir/`` which contains level 2A files to create a 200 x 200 km output tile in the UTM36S projection at 20 m resoluton, input:

.. code-block:: console
    
    s2m mosaic -te 700000 7900000 900000 8100000 -e 32736 -res 20 /path/to/DATA_dir/

To do the same operation, but specifying an output directory, a name to prepend to outputs from this tile, and performing inter-scene colour balancing and corrections to the sen2cor mask, input:

.. code-block:: console
    
    s2m mosaic -te 700000 7900000 900000 8100000 -e 32736 -res 20 -o /path/to/output/ -n my_output -b -c /path/to/DATA_dir/


