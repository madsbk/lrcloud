Lightroom Cloud Extension
=========================

This project extend Adobe Lightroom with cloud support making it possible to access a catalog from different machines safely without corrupting the catalog.

**Features**:
  * Have a catalog file in a shared location, such as a folder in Google Drive, Dropbox, or a NAS, and have lrcloud synchronize the catalog between a local and the shared location.
  * Only synchronizing the changes not the whole catalog
  * Support Smart Previews
  * On-the-fly catalog compression

**Current limitations**:
  * The paths in the shared catalog are not converted thus a catalog cannot be shared between Window and OSX.
  * No GUI
  * No simultaneous catalog access


Usage
-----
.. note:: Please note that `lrcloud` is still in **beta** so backup your catalog frequently :)

.. code:: bash

    $ python -m lrcloud -h
    usage: __main__.py [-h] [--init-push-to-cloud | --init-pull-from-cloud]
                       [--cloud-catalog CLOUD_CATALOG]
                       [--local-catalog LOCAL_CATALOG]
                       [--lightroom-exec LIGHTROOM_EXEC | --lightroom-exec-debug LIGHTROOM_EXEC_DEBUG]
                       [-v] [--no-smart-previews] [--config-file CONFIG_FILE]
                       [--diff-cmd DIFF_CMD] [--patch-cmd PATCH_CMD]

    Cloud extension to Lightroom

    optional arguments:
      -h, --help            show this help message and exit
      --init-push-to-cloud  Initiate the local catalog and push it to the cloud
                            (default: False)
      --init-pull-from-cloud
                            Download the cloud catalog and initiate a
                            corresponding local catalog (default: False)
      --cloud-catalog CLOUD_CATALOG
                            The cloud/shared catalog file e.g. located in Google
                            Drive or Dropbox (default: None)
      --local-catalog LOCAL_CATALOG
                            The local Lightroom catalog file (default: None)
      --lightroom-exec LIGHTROOM_EXEC
                            The Lightroom executable file (default: None)
      --lightroom-exec-debug LIGHTROOM_EXEC_DEBUG
                            Instead of running Lightroom, append data to the end
                            of the catalog file (default: None)
      -v, --verbose         Increase output verbosity (default: False)
      --no-smart-previews   Don't Sync Smart Previews (default: False)
      --config-file CONFIG_FILE
                            Path to the configure (.ini) file (default:
                            /home/madsbk/.lrcloud.ini)
      --diff-cmd DIFF_CMD   The command that given two files, $in1 and $in2,
                            produces a diff file $out (default: ./jdiff -f $in1
                            $in2 $out)
      --patch-cmd PATCH_CMD
                            The command that given a file, $in1, and a path,
                            $patch, produces a file $out (default: ./jptch $in1
                            $patch $out)
