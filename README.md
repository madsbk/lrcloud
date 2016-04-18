# Lightroom Cloud Extension

This project extent Adobe Lightroom with cloud support making it possible to access a catalog from different machines safely without corrupting the catalog.

##### Features:
  * Have a catalog file in a shared location, such as a folder in Google Drive, Dropbox, or a NAS, and have lrcloud synchronize the catalog between a local and the shared location.
  * A single executable
  * Support Smart Previews 
  * On-the-fly catalog compression 

##### Current limitations:
  * The paths the photos in a shared catalog have to be identical thus a catalog cannot be shared between Window and OSX.
  * No GUI
  * No simultaneous catalog access


Usage
-----
##### Please note that `lrcloud` is still in beta and is not ready for production

```
./lrcloud.py --help
usage: lrcloud.py [-h] [--cloud-catalog CLOUD_CATALOG]
                  [--local-catalog LOCAL_CATALOG]
                  [--lightroom-exec LIGHTROOM_EXEC] [-v] [--no-smart-previews]
                  [--config-file CONFIG_FILE]

Cloud extension to Lightroom

optional arguments:
  -h, --help            show this help message and exit
  --cloud-catalog CLOUD_CATALOG
                        The cloud/shared catalog file e.g. located in Google
                        Drive or Dropbox (default: None)
  --local-catalog LOCAL_CATALOG
                        The local Lightroom catalog file (default: None)
  --lightroom-exec LIGHTROOM_EXEC
                        The Lightroom executable file (default: None)
  -v, --verbose         Increase output verbosity (default: False)
  --no-smart-previews   Don't Sync Smart Previews (default: False)
  --config-file CONFIG_FILE
                        Path to the configure (.ini) file (default:
                        /home/madsbk/.lrcloud.ini)
```
