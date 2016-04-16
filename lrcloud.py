#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess
import logging
from os.path import join, basename

def lock_file(filename):
    """Locks the file by writing a '.lock' file.
       Returns True when the file is locked and
       False when the file was locked already"""

    lockfile = "%s.lock"%filename
    if os.path.isfile(lockfile):
        return False
    else:
        with open(lockfile, "w"):
            pass
    return True

def unlock_file(filename):
    """Unlocks the file by remove a '.lock' file.
       Returns True when the file is unlocked and
       False when the file was unlocked already"""

    lockfile = "%s.lock"%filename
    if os.path.isfile(lockfile):
        os.remove(lockfile)
        return True
    else:
        return False

def main(args):
    cloud_catalog = join(args.cloud_dir,basename(args.catalog))

    #Let's "lock" the local catalog
    if not lock_file(args.catalog):
        raise RuntimeError("The catalog %s is locked!"%args.catalog)

    #Let's "lock" the cloud catalog
    if not lock_file(cloud_catalog):
        raise RuntimeError("The cloud catalog %s is locked!"%cloud_catalog)

    #Let's make sure that the local catalog exist and is readable
    with open(args.catalog, "r"):
        #TODO: integrity check and get version
        pass

    if os.path.isfile(cloud_catalog):#The cloud is not empty

        #Backup the local catalog (overwriting old backup)
        try:
            os.remove("%s.backup"%args.catalog)
            logging.info("Removed old backup: %s.backup"%args.catalog)
        except OSError:
            pass        
        logging.info("Backup: %s => %s.backup"%(args.catalog, args.catalog))
        shutil.move(args.catalog, "%s.backup"%args.catalog)

        #Copy from cloud to local
        logging.info("Copy catalog - cloud to local: %s => %s"%(cloud_catalog, args.catalog))
        shutil.copy2(cloud_catalog, args.catalog)

    #Let's unlock the local catalog so that Lightrome can read it
    logging.info("Unlocking local catalog: %s"%(args.catalog))
    unlock_file(args.catalog)
    
    #Now we can start Lightroom
    logging.info("Starting Lightroom: %s"%args.lightroom_exec)
    if args.lightroom_exec is not None:
        subprocess.call(args.lightroom_exec)
    logging.info("Lightroom exit")

    #Copy from local to cloud
    logging.info("Copy catalog - local to cloud: %s => %s"%(args.catalog, cloud_catalog))
    shutil.copy2(args.catalog, cloud_catalog)

    #Finally,let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(args.catalog))
    unlock_file(args.catalog)
    logging.info("Unlocking cloud catalog: %s"%(cloud_catalog))
    unlock_file(cloud_catalog)


def expand_path(parser, path):
    """
    Expand then given path.

    Such as expanding the tilde in "~/bohrium", thereby providing
    the absolute path to the directory "bohrium" in the home folder.
    """

    path = os.path.expanduser(path)
    if os.path.isdir(path):
        return os.path.abspath(path)
    else:
        parser.error("The path %s does not exist!" % path)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Cloud extension to Lightroom')
    parser.add_argument(
        '--cloud-dir',
        help='Path to the cloud directory e.g. a Google Drive '\
             'or a Dropbox folder',
        type=lambda x: expand_path(parser, x)
    )
    parser.add_argument(
        '--catalog',
        help='The Lightroom catalog file',
        type=str
    )
    parser.add_argument(
        '--lightroom_exec',
        help='The Lightroom executable file',
        type=str
    )
    parser.add_argument(
        '-v', '--verbose',
        help='Increase output verbosity',
        action="store_true"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    main(args)
