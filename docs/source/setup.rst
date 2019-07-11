Setup instructions
==================

Requirements
------------

This toolset is written for use in Linux.

You will need access to a PC or server with at least:

* Python 3
* `sen2mosaic <https://bitbucket.org/sambowers/sen2mosaic/>`
* 8 GB of RAM to run sen2cor.

Installing Anaconda Python
--------------------------

These tools are written in Python. We recommend the Anaconda distribution of Python, which contains all the modules necessary to run these scripts.

To install Anaconda Python, open a terminal window, change directory to the location you'd like to install Anaconda Python, and run the following commands:

.. code-block:: console
    
    wget https://repo.anaconda.com/archive/Anaconda3-2019.03-Linux-x86_64.sh
    chmod +x Anaconda3-2019.03-Linux-x86_64.sh
    ./Anaconda3-2019.03-Linux-x86_64.sh

If this has functioned, on executing ``python`` in a terminal window, you should ssee the following:

.. code-block:: console
    
    Python 2.7.14 |Anaconda, Inc.| (default, Dec  7 2017, 17:05:42) 
    [GCC 7.2.0] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    >>> 

Setting up your Anaconda environment
------------------------------------

.. note:: The Anaconda environment required for sen1mosaic and sen2mosaic is identical. If you already have a sen1mosaic environment set up, it can be used in place of a new environment.

To ensure you are working with the appropriate version of Python as well as the correct modules, we recommend that you create an Anaconda virtual environment set up for running ``sen2mosaic``. This is done by running the following commands in your terminal or the Anaconda prompt (recommended procedure):

.. code-block:: console
    
    conda create -n sen2mosaic -c conda-forge python=3.7 scipy pandas psutil scikit-image gdal opencv pyshp

Activate the ``sen2mosaic`` environment whenever opening a new terminal window by running this command:

.. code-block:: console
    
    conda activate sen2mosaic

Installing sen2cor
------------------

sen2cor is an ESA program to perform atmospheric correction and cloud masking of Sentinel-2 level 1C images. It generates a new file containing bottom of atmosphere reflectance values and a cloud mask.

For further details and up-to-date installation instructions, see the `sen2cor website <http://step.esa.int/main/third-party-plugins-2/sen2cor/>`_.

At the time of writing, sen2cor can be installed using the following commands. sen2cor must be installed after Anaconda Python. Open a terminal window, change directory to the location you'd like sen2cor to be installed, and run the following commands:

.. code-block:: console
    
    wget http://step.esa.int/thirdparties/sen2cor/2.8.0/Sen2Cor-02.08.00-Linux64.run
    chmod +x Sen2Cor-02.08.00-Linux64.run
    ./Sen2Cor-02.08.00-Linux64.run

Once complete, you need to reference this software in your .bashrc file as follows:

.. code-block:: console
    
    echo "source ~/Sen2Cor-02.08.00-Linux64/L2A_Bashrc" >> ~/.bashrc
    exec -l $SHELL

To test the installation, type ``L2A_Process --help`` in a terminal window to show running instructions. You should see something that looks like the following:

.. code-block:: console
    
    usage: L2A_Process.py [-h] [--mode MODE] [--resolution {10,20,60}]
                        [--datastrip DATASTRIP] [--tile TILE]
                        [--output_dir OUTPUT_DIR] [--work_dir WORK_DIR]
                        [--img_database_dir IMG_DATABASE_DIR]
                        [--res_database_dir RES_DATABASE_DIR]
                        [--processing_centre PROCESSING_CENTRE]
                        [--archiving_centre ARCHIVING_CENTRE]
                        [--processing_baseline PROCESSING_BASELINE] [--raw]
                        [--tif] [--sc_only] [--cr_only] [--debug]
                        [--GIP_L2A GIP_L2A] [--GIP_L2A_SC GIP_L2A_SC]
                        [--GIP_L2A_AC GIP_L2A_AC] [--GIP_L2A_PB GIP_L2A_PB]
                        input_dir

    Sentinel-2 Level 2A Processor (Sen2Cor). Version: 2.8.0, created: 2019.02.20,
    supporting Level-1C product version 14.2 - 14.5.

    positional arguments:
    input_dir             Directory of Level-1C input

    optional arguments:
    -h, --help            show this help message and exit
    --mode MODE           Mode: generate_datastrip, process_tile
    --resolution {10,20,60}
                            Target resolution, can be 10, 20 or 60m. If omitted,
                            only 20 and 10m resolutions will be processed
    --datastrip DATASTRIP
                            Datastrip folder
    --tile TILE           Tile folder
    --output_dir OUTPUT_DIR
                            Output directory
    --work_dir WORK_DIR   Work directory
    --img_database_dir IMG_DATABASE_DIR
                            Database directory for L1C input images
    --res_database_dir RES_DATABASE_DIR
                            Database directory for results and temporary products
    --processing_centre PROCESSING_CENTRE
                            Processing centre as regex: ^[A-Z_]{4}$, e.g "SGS_"
    --archiving_centre ARCHIVING_CENTRE
                            Archiving centre as regex: ^[A-Z_]{4}$, e.g. "SGS_"
    --processing_baseline PROCESSING_BASELINE
                            Processing baseline in the format: "dd.dd", where
                            d=[0:9]
    --raw                 Export raw images in rawl format with ENVI hdr
    --tif                 Export raw images in TIFF format instead of JPEG-2000
    --sc_only             Performs only the scene classification at 60 or 20m
                            resolution
    --cr_only             Performs only the creation of the L2A product tree, no
                            processing
    --debug               Performs in debug mode
    --GIP_L2A GIP_L2A     Select the user GIPP
    --GIP_L2A_SC GIP_L2A_SC
                            Select the scene classification GIPP
    --GIP_L2A_AC GIP_L2A_AC
                            Select the atmospheric correction GIPP
    --GIP_L2A_PB GIP_L2A_PB
                            Select the processing baseline GIPP

Installing sentinelsat
----------------------

Sentinelsat is the toolset used to access data from the Sentinel-2 archive at the `Copernicus Open Access Data Hub <https://scihub.copernicus.eu/>`_.

Up-to-date installation instructions can be found `here <https://pypi.python.org/pypi/sentinelsat>`_.

At the time of writing, the installation process is as follows:

.. code-block:: console

    pip install sentinelsat

Installing sen2mosaic
---------------------

sen2mosaic can be downloaded to a machine from its `repository <https://bitbucket.org/sambowers/sen2mosaic/>`_ . To do this, open a terminal window and input:

.. code-block:: console

    git clone https://sambowers@bitbucket.org/sambowers/sen2mosaic.git

To install sen2mosaic, navigate to the sen2mosaic directory and run the following within your sen2mosaic environment.

.. code-block:: console
    
    python setup.py install
    
To avoid having to reference the full path of the Python scripts in sen2mosaic, it's a good idea add the following line to your ``.bashrc`` file:

.. code-block:: console

    echo "alias s2m='_s2m() { python ~/sen2mosaic/cli/\"\$1\".py \$(shift; echo \"\$@\") ;}; _s2m'" >> ~/.bashrc
   
Is there a Dockerfile?
----------------------

Coming soon!
   
Where do I get help?
--------------------

For help installing sen2cor and sen2three, it's best to refer to the `ESA STEP forum <http://forum.step.esa.int/>`_. For assistance in setting up and using sen2mosaic, email `sam.bowers@ed.ac.uk <mailto:sam.bowers@ed.ac.uk>`_.

