Setup instructions
==================

Requirements
------------

This toolset is written for use in a Linux environment. You will need a PC or server with at least 8 GB of RAM to process Sentinel-2 data to level 2A. To process Sentinel-2 data to level 3A you will require 32 to 128 GB of RAM to create cloud-free composite images with Sen2three, depending on how many images you aim to combine. The latter stages of this processing chain are beyond the capabilities of most PCs, and likely to require use of a large server.

Installing Anaconda Python
--------------------------

The ESA tools sen2cor and sen2three are at present heavily reliant upon a particular version of the Anaconda Python distribution (v 4.2.0). At the time of writing, newer versions of Anaconda Python are incompatable with sen2cor and sen2three, though this may well change in future.

To install Anaconda Python, open a terminal window, change directory to the location you'd like to install Anaconda Python, and run the following commands:

::
    wget https://repo.continuum.io/archive/Anaconda2-4.2.0-Linux-x86_64.sh

    bash Anaconda2-4.2.0-Linux-x86_64.sh

Once complete, you'll need to add this version of Python to your .bashrc file as follows:

::
    # Substitute root for the path to your system's installation and .bashrc file.
    echo 'export PATH="/root/anaconda2/bin:$PATH"' >> /root/.bashrc
    exec -l $SHELL


Installing sen2cor
------------------

sen2cor is an ESA program to perform atmospheric correction and cloud masking of Sentinel-2 level 1C images. It generates a new file containing bottom of atmosphere reflectance values and a cloud mask.

For further details and up-to-date installation instructions, see [http://step.esa.int/main/third-party-plugins-2/sen2cor/](http://step.esa.int/main/third-party-plugins-2/sen2cor/).

At the time of writing, sen2cor can be installed using the following commands. sen2cor must be installed after Anaconda Python. Open a terminal window, change directory to the location you'd like sen2cor to be installed, and run the following commands:

::
    wget http://step.esa.int/thirdparties/sen2cor/2.3.1/sen2cor-2.3.1.tar.gz
    tar -xvzf sen2cor-2.3.1.tar.gz
    rm sen2cor-2.3.1.tar.gz
    cd sen2cor-2.3.1
    python setup.py install

Once complete, you need to reference this software in your .bashrc file as follows:

::
    # Substitute root for the path to your system's installation and .bashrc file.
    echo "source /root/sen2cor/L2A_Bashrc" >> /root/.bashrc
    exec -l $SHELL

To test the installation, type the following in a terminal window to show running instructions:

::
    L2A_Process --help
    usage: L2A_Process [-h] [--resolution {10,20,60}] [--sc_only] [--cr_only]
                       [--refresh] [--GIP_L2A GIP_L2A] [--GIP_L2A_SC GIP_L2A_SC]
                       [--GIP_L2A_AC GIP_L2A_AC]
                       directory
    
    Sentinel-2 Level 2A Processor (Sen2Cor). Version: 2.3.1, created: 2017.02.03,
    supporting Level-1C product version: 14.
    
    positional arguments:
      directory             Directory where the Level-1C input files are located
    
    optional arguments:
      -h, --help            show this help message and exit
      --resolution {10,20,60}
                            Target resolution, can be 10, 20 or 60m. If omitted,
                            all resolutions will be processed
      --sc_only             Performs only the scene classification at 60 or 20m
                            resolution
       --cr_only             Performs only the creation of the L2A product tree, no processing
      --refresh             Performs a refresh of the persistent configuration
                            before start
      --GIP_L2A GIP_L2A     Select the user GIPP
      --GIP_L2A_SC GIP_L2A_SC
                            Select the scene classification GIPP
      --GIP_L2A_AC GIP_L2A_AC
                            Select the atmospheric correction GIPP
    


Installing sen2three
--------------------

sen2three is an ESA program to combine multiple level 2A images from Sentinel-2 into cloud-free composite images. It generates a new file containing the best quality cloud-free image that it can construct from available imagery. Note: this processing chain requires sen2three version 1.1.0 or later.

For further details and up-to-date installation instructions, see [http://step.esa.int/main/third-party-plugins-2/sen2three/](http://step.esa.int/main/third-party-plugins-2/sen2three/).

At the time of writing, sen2three can be installed using the following commands. sen2three must be installed after Anaconda Python. Open a terminal window, change directory to the location you'd like sen2three to be installed, and run the following commands:

::
    wget http://step.esa.int/thirdparties/sen2three/1.0.1/sen2three-1.1.0.tar.gz
    tar sen2three-1.1.0.tar.gz
    rm sen2three-1.1.0.tar.gz
    cd sen2three-1.1.0
    python setup.py install

Once complete, you need to reference this software in your .bashrc file as follows:

::
    # Substitute root for the path to your system's installation and .bashrc file.
    echo "source /root/sen2three/L3_Bashrc" >> /root/.bashrc
    exec -l $SHELL


To test the installation, type the following in a terminal window to show running instructions:

::
    L3_Process --help
    usage: L3_Process [-h] [--resolution {10,20,60}] [--clean] directory
    
    Sentinel-2 Level 3 Processor (Sen2Three), 1.1.0, created: 2017.07.01,
    supporting Level-1C product version: 14.
    
    positional arguments:
      directory             Directory where the Level-2A input files are located
    
    optional arguments:
      -h, --help            show this help message and exit
      --resolution {10,20,60}
                            Target resolution, can be 10, 20 or 60m. If omitted,
                            all resolutions will be processed
      --clean               Removes the L3 product in the target directory before processing. Be careful!

Installing sentinelsat
----------------------

Sentinelsat is the toolset used to access data from the Sentinel-2 archive at the [Copernicus Open Access Data Hub](https://scihub.copernicus.eu/).

Up-to-date installation instructions can be found at: [https://pypi.python.org/pypi/sentinelsat](https://pypi.python.org/pypi/sentinelsat).

At the time of writing, the installation process was as follows:

::
    To complete

Installing sen2mosaic
---------------------

TBD!

Where do I get help?
--------------------

For help installing sen2cor and sen2three, refer to the [ESA STEP forum](http://forum.step.esa.int/). For help with sen2mosaic, email [sam.bowers@ed.ac.uk](mailto:sam.bowers@ed.ac.uk).

