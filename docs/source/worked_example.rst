A worked example on the command line
====================================

Here we'll show you by example how the sen2mosaic processing chain works in practice. We will focus on an example from southern Mozambique, with the aim of creating a cloud-free composite GeoTiff product for the area **500,000 - 600,000 m E** and **7,550,000 - 7,650,000 m N** ( **UTM 36S** ). This area is covered by Sentinel-2 tiles **36KWA** and **36KWB**. We'll limit this mosaic to the early dry season ( **May and June** ), in anticipation of multiple seasonally-specific mosaics improving classification accuracy. We'll download data from the year **2017**.

Preparation
-----------

First ensure that you've followed :ref:`setup` successfully.

Open a terminal, and use ``cd`` to navigate to the location you'd like to store data.

.. code-block:: console
    
    cd /home/user/DATA
    mkdir worked_example
    cd worked_example

Use mkdir to make a separate folder for each of the granules you intend to download.

.. code-block:: console
    
    mkdir 36KWA
    mkdir 36KWB
    
Here we'll demonstrate the process for the tile 36KWA. We'll leave 36KWB for you to do without guidance.

To begin, navigate to the 36KWA folder.

.. code-block:: console
    
    cd 36KWA

Downloading data
----------------

The first step is to download Sentinel-2 level 1C data from the `Copernicus Open Access Data Hub <https://scihub.copernicus.eu/>`_.

For this we use the ``L1C.py`` tool. We will need to specify a Scihub username and password (sign up for an account at `Scihub <https://scihub.copernicus.eu/>`_), the tile to download, a start and end date in the format YYYYMMDD, and a maximum degree of cloud cover to download. For the purposes of this demonstration, we'll set maximum cloud cover to 30 %.

These options can be encoded as follows:

.. code-block:: console
    
    python /path/to/sen2mosaic/L1C.py -u user.name -p supersecret -t 36KWA -s 20170501 -e 20170630 -c 30

As we didn't specify the option ``-o`` (``--output``), data will output to the current working directory. We also didn't include the ``-r`` (``--remove``) flag, meaning that intermediate .zip files downloaded from the internet won't be deleted. This can quickly result in large volumes of data building up, so if you're limited by disk space use the ``-r`` flag.

Wait for all files to finish downloading before proceeding to the next step. By the time the processing is complete, your ``36KWA/`` directory should contain the following files (show files in the currenty working directory with the command ``ls``).

.. code-block:: console
    ls
    S2A_MSIL1C_20170506T074241_N0205_R049_T36KWA_20170506T075325.SAFE
    S2A_MSIL1C_20170506T074241_N0205_R049_T36KWA_20170506T075325.zip
    S2A_MSIL1C_20170516T072621_N0205_R049_T36KWA_20170516T075513.SAFE
    S2A_MSIL1C_20170516T072621_N0205_R049_T36KWA_20170516T075513.zip
    S2A_MSIL1C_20170519T075221_N0205_R092_T36KWA_20170519T080547.SAFE
    S2A_MSIL1C_20170519T075221_N0205_R092_T36KWA_20170519T080547.zip
    S2A_MSIL1C_20170526T074241_N0205_R049_T36KWA_20170526T074901.SAFE
    S2A_MSIL1C_20170526T074241_N0205_R049_T36KWA_20170526T074901.zip
    S2A_MSIL1C_20170529T073611_N0205_R092_T36KWA_20170529T075550.SAFE
    S2A_MSIL1C_20170529T073611_N0205_R092_T36KWA_20170529T075550.zip
    S2A_MSIL1C_20170605T072621_N0205_R049_T36KWA_20170605T075534.SAFE
    S2A_MSIL1C_20170605T072621_N0205_R049_T36KWA_20170605T075534.zip
    S2A_MSIL1C_20170608T075211_N0205_R092_T36KWA_20170608T080546.SAFE
    S2A_MSIL1C_20170608T075211_N0205_R092_T36KWA_20170608T080546.zip
    S2A_MSIL1C_20170628T075211_N0205_R092_T36KWA_20170628T080542.SAFE
    S2A_MSIL1C_20170628T075211_N0205_R092_T36KWA_20170628T080542.zip

Atmopsheric correction and cloud masking
----------------------------------------

The next step is to perform atmospheric correction (removes the effects of the atmosphere on refectance values of images) and cloud masking (identififies clouds in images.) to generate Sentinel-2 level 2A data. We do this with the ESA program ``sen2cor``.

To perform atmospheric correction and cloud masking we call the tool ``L2A.py``. We need to specify the input files (all follow the format ``*_MSIL1C_*.SAFE``).

To run the process, we need to submit the following line:

.. code-block:: console

    python ~/DATA/sen2mosaic/sen2mosaic/L2A.py /home/sbowers3/DATA/worked_example/36KWA/*_MSIL1C_*.SAFE

This command will loop through each Sentinel-2 level 1C file and process them one at a time. You might alternatively want to specify a single level 1C .SAFE file, and run several commands similtaneously. Bear in mind that this will require access to a large quanity of memory.

Here we didn't specify the options ``-o`` (``--output_dir``) and ``--g`` (``--gipp``), which can be used to output data to a location other than the directory containing input files, or the ``-r`` (``--remove``) option, which would delete Sentinel-2 level 1C data once data is finished processing.

Wait for all files to be processed to level 2A before proceeding. If you run ``ls`` again, your ``36KWA/`` directory should now contain a new set of files:

.. code-block:: console
    ls
    S2A_MSIL1C_20170506T074241_N0205_R049_T36KWA_20170506T075325.SAFE
    S2A_MSIL1C_20170506T074241_N0205_R049_T36KWA_20170506T075325.zip
    S2A_MSIL1C_20170516T072621_N0205_R049_T36KWA_20170516T075513.SAFE
    S2A_MSIL1C_20170516T072621_N0205_R049_T36KWA_20170516T075513.zip
    S2A_MSIL1C_20170519T075221_N0205_R092_T36KWA_20170519T080547.SAFE
    S2A_MSIL1C_20170519T075221_N0205_R092_T36KWA_20170519T080547.zip
    S2A_MSIL1C_20170526T074241_N0205_R049_T36KWA_20170526T074901.SAFE
    S2A_MSIL1C_20170526T074241_N0205_R049_T36KWA_20170526T074901.zip
    S2A_MSIL1C_20170529T073611_N0205_R092_T36KWA_20170529T075550.SAFE
    S2A_MSIL1C_20170529T073611_N0205_R092_T36KWA_20170529T075550.zip
    S2A_MSIL1C_20170605T072621_N0205_R049_T36KWA_20170605T075534.SAFE
    S2A_MSIL1C_20170605T072621_N0205_R049_T36KWA_20170605T075534.zip
    S2A_MSIL1C_20170608T075211_N0205_R092_T36KWA_20170608T080546.SAFE
    S2A_MSIL1C_20170608T075211_N0205_R092_T36KWA_20170608T080546.zip
    S2A_MSIL1C_20170628T075211_N0205_R092_T36KWA_20170628T080542.SAFE
    S2A_MSIL1C_20170628T075211_N0205_R092_T36KWA_20170628T080542.zip
    ...

Generating cloud-free composite images
--------------------------------------



    