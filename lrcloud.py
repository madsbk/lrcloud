#!/usr/bin/env python

import argparse
import os
import sys
import shutil
import subprocess
import logging
import distutils.dir_util
from os.path import join, basename, dirname, isfile
import traceback
import zipfile
from zipfile import ZIP_DEFLATED
import tempfile


if sys.version_info >= (3,):
    import configparser as cparser
else:
    import ConfigParser as cparser


def lock_file(filename):
    """Locks the file by writing a '.lock' file.
       Returns True when the file is locked and
       False when the file was locked already"""

    lockfile = "%s.lock"%filename
    if isfile(lockfile):
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
    if isfile(lockfile):
        os.remove(lockfile)
        return True
    else:
        return False


def copy_smart_previews(local_catalog, cloud_catalog, local2cloud=True):
    """Copy Smart Previews from local to cloud or
       vica versa when 'local2cloud==False'
       NB: nothing happens if source dir doesn't exist"""

    lcat_noext = local_catalog[0:local_catalog.rfind(".lrcat")]
    ccat_noext = cloud_catalog[0:cloud_catalog.rfind(".lrcat")]
    lsmart = join(dirname(local_catalog),"%s Smart Previews.lrdata"%basename(lcat_noext))
    csmart = join(dirname(cloud_catalog),"%s Smart Previews.lrdata"%basename(ccat_noext))
    if local2cloud and os.path.isdir(lsmart):
        logging.info("Copy Smart Previews - local to cloud: %s => %s"%(lsmart, csmart))
        distutils.dir_util.copy_tree(lsmart,csmart, update=1)
    elif os.path.isdir(csmart):
        logging.info("Copy Smart Previews - cloud to local: %s => %s"%(csmart, lsmart))
        distutils.dir_util.copy_tree(csmart,lsmart, update=1)


def copy_catalog(local_catalog, cloud_catalog, local2cloud=True):
    """Copy catalog files from local to cloud or
       vica versa when 'local2cloud==False'
    """

    (lcat, ccat) = (local_catalog, cloud_catalog)

    #Find the source and destination catalog
    if local2cloud:
        logging.info("Copy catalog - local to cloud: %s => %s"%(lcat, ccat))
        (src, dst) = (lcat, ccat)
    else:
        logging.info("Copy catalog - cloud to local: %s => %s"%(ccat, lcat))
        (src, dst) = (ccat, lcat)

    (szip, dzip) = (src.endswith(".zip"), dst.endswith(".zip"))

    if szip and dzip:#If both zipped, we can simply use copy
        shutil.copy2(src, dst)
    elif szip:
        with zipfile.ZipFile(src, mode='r') as z:
            tmpdir = tempfile.mkdtemp()
            try:
                z.extractall(tmpdir)
                if len(z.namelist()) != 1:
                    raise RuntimeError("The zip file '%s' should only have one "\
                                       "compressed file")
                tmpfile = join(tmpdir,z.namelist()[0])
                try:
                    os.remove(dst)
                except OSError:
                    pass
                shutil.move(tmpfile, dst)
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
    elif dzip:
        with zipfile.ZipFile(dst, mode='w', compression=ZIP_DEFLATED) as z:
            z.write(src, arcname=basename(src))
    else:#None of them are zipped
        shutil.copy2(src, dst)


def main(args):
    lcat = args.local_catalog
    ccat = args.cloud_catalog

    #Let's "lock" the local catalog
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Let's "lock" the cloud catalog
    if not lock_file(ccat):
        raise RuntimeError("The cloud catalog %s is locked!"%ccat)

    if isfile(ccat):#The cloud is not empty

        #Backup the local catalog (overwriting old backup)
        if isfile(lcat):
            try:
                logging.info("Removed old backup: %s.backup"%lcat)
                os.remove("%s.backup"%lcat)
            except OSError:
                pass
            logging.info("Backup: %s => %s.backup"%(lcat, lcat))
            shutil.move(lcat, "%s.backup"%lcat)

        #Copy from cloud to local
        copy_catalog(lcat, ccat, local2cloud=False)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=False)

    #Let's unlock the local catalog so that Lightrome can read it
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)

    #Now we can start Lightroom
    logging.info("Starting Lightroom: %s %s"%(args.lightroom_exec, lcat))
    if args.lightroom_exec is not None:
        subprocess.call([args.lightroom_exec, lcat])
    logging.info("Lightroom exit")

    #Copy from local to cloud
    copy_catalog(lcat, ccat, local2cloud=True)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally,let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)
    logging.info("Unlocking cloud catalog: %s"%(ccat))
    unlock_file(ccat)


def read_config_file(args):
    """Reading the configure file and adds non-existing attributes to 'args'"""

    if args.config_file is None or not isfile(args.config_file):
        return

    logging.info("Reading configure file: %s"%args.config_file)

    config = cparser.ConfigParser()
    config.read(args.config_file)
    if not config.has_section('lrcloud'):
        raise RuntimeError("Configure file has no [lrcloud] section!")

    for (name, value) in config.items('lrcloud'):
        if value == "True":
            value = True
        elif value == "False":
            value = False
        if getattr(args, name) is None:
            setattr(args, name, value)


def write_config_file(args):
    """Writing the configure file with the attributes in 'args'"""

    logging.info("Writing configure file: %s"%args.config_file)
    if args.config_file is None:
        return

    #Let's add each attribute of 'args' to the configure file
    config = cparser.ConfigParser()
    config.add_section("lrcloud")
    for p in [x for x in dir(args) if not x.startswith("_")]:
        value = getattr(args, p)
        if value is not None:
            config.set('lrcloud', p, str(value))

    with open(args.config_file, 'w') as f:
        config.write(f)


def parse_arguments():
    """Return arguments"""

    def default_config_path():
        """Returns the platform specific default location of the configure file"""

        if os.name == "nt":
            return join(os.getenv('APPDATA'), "lrcloud.ini")
        else:
            return join(os.path.expanduser("~"), ".lrcloud.ini")

    parser = argparse.ArgumentParser(
                description='Cloud extension to Lightroom',
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
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
        '--lightroom-exec',
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
    parser.add_argument(
        '--config-file',
        help="Path to the configure (.ini) file",
        type=str,
        default=default_config_path()
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    read_config_file(args)
    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)

    if lcat is None:
        parser.error("No local catalog specified, use --local-catalog")
        raise argparse.ArgumentError
    if ccat is None:
        parser.error("No cloud catalog specified, use --cloud-catalog")
        raise argparse.ArgumentError

    if not isfile(lcat) and not isfile(ccat):
        parser.error("No catalog exist! Either a local "\
                     "or a cloud catalog must exist")
        raise argparse.ArgumentError

    #Make sure we don't overwrite a modified local catalog
    #NB: we allow a small different (1 msec)) because of OS limitations
    if isfile(lcat) and isfile(ccat):
        if(os.path.getmtime(lcat) - 0.001 > os.path.getmtime(ccat)):
            parser.error("The local catalog is newer than the cloud catalog. "
                         "Please remove one of them: '%s' or '%s'"%(lcat,ccat))
            raise argparse.ArgumentError
    return args


if __name__ == "__main__":

    args = parse_arguments()

    try:
        main(args)
    finally:
        unlock_file(args.local_catalog)
        unlock_file(args.cloud_catalog)

    write_config_file(args)


