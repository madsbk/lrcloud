#!/usr/bin/env python

import argparse
import os
import shutil
import subprocess
import logging
import distutils.dir_util
from os.path import join, basename, dirname

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

def copy_smart_previews(local_catalog, cloud_catalog, local2cloud=True):
    """Copy Smart Previews from local to cloud or
       vica versa when 'local2cloud==False' """
    
    lcat_noext = local_catalog[0:local_catalog.rfind(".lrcat")]
    ccat_noext = cloud_catalog[0:cloud_catalog.rfind(".lrcat")]
    lsmart = join(dirname(local_catalog),"%s Smart Previews.lrdata"%basename(lcat_noext))
    csmart = join(dirname(cloud_catalog),"%s Smart Previews.lrdata"%basename(ccat_noext))
    if local2cloud:
        logging.info("Copy Smart Previews - local to cloud: %s => %s"%(lsmart, csmart))
        distutils.dir_util.copy_tree(lsmart,csmart, update=1)
    else:
        logging.info("Copy Smart Previews - cloud to local: %s => %s"%(csmart, lsmart))
        distutils.dir_util.copy_tree(csmart,lsmart, update=1)

def main(args):
    lcat = args.local_catalog
    ccat = args.cloud_catalog
    
    #Let's "lock" the local catalog
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Let's "lock" the cloud catalog
    if not lock_file(ccat):
        raise RuntimeError("The cloud catalog %s is locked!"%ccat)

    #Let's make sure that the local catalog exist and is readable
    with open(lcat, "r"):
        #TODO: integrity check and get version
        pass

    if os.path.isfile(ccat):#The cloud is not empty

        #Backup the local catalog (overwriting old backup)
        try:
            os.remove("%s.backup"%lcat)
            logging.info("Removed old backup: %s.backup"%lcat)
        except OSError:
            pass        
        logging.info("Backup: %s => %s.backup"%(lcat, lcat))
        shutil.move(lcat, "%s.backup"%lcat)

        #Copy from cloud to local
        logging.info("Copy catalog - cloud to local: %s => %s"%(ccat, lcat))
        shutil.copy2(ccat, lcat)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(ccat, lcat, local2cloud=False)

    #Let's unlock the local catalog so that Lightrome can read it
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)
    
    #Now we can start Lightroom
    logging.info("Starting Lightroom: %s"%args.lightroom_exec)
    if args.lightroom_exec is not None:
        subprocess.call(args.lightroom_exec)
    logging.info("Lightroom exit")

    #Copy from local to cloud
    logging.info("Copy catalog - local to cloud: %s => %s"%(lcat, ccat))
    shutil.copy2(lcat, ccat)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally,let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)
    logging.info("Unlocking cloud catalog: %s"%(ccat))
    unlock_file(ccat)


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
        '--cloud-catalog',
        help='The cloud/shared catalog file e.g. located in Google Drive or Dropbox',
        type=lambda x: os.path.expanduser(x)
    )
    parser.add_argument(
        '--local-catalog',
        help='The local Lightroom catalog file',
        type=lambda x: os.path.expanduser(x)
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
    parser.add_argument(
        '--no-smart-previews',
        help="Don't Sync Smart Previews",
        action="store_true"
    )
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    main(args)
