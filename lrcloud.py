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
import hashlib
from functools import partial
from datetime import datetime

DATETIME_FORMAT='%Y-%m-%d %H:%M:%S.%f'

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
                                       "compressed file"%src)
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


def catalog2meta_file(catalog):
    """Return the meta-data file name associated with 'catalog' """
    return "%s.lrcloud.ini"%catalog


def hashsum(filename):
    """Return a hash of the file From <http://stackoverflow.com/a/7829658>"""

    with open(filename, mode='rb') as f:
        d = hashlib.sha1()
        for buf in iter(partial(f.read, 2**20), b''):
            d.update(buf)
    return d.hexdigest()


def write_local_meta_file(args):
    lcat = args.local_catalog
    mfile = catalog2meta_file(lcat)

    #Let's hash the local catalog file
    lcat_hash = hashsum(lcat)
    logging.info("The hash of the local catalog file: %s"%lcat_hash)

    #Let's write the meta-data for the 'master' catalog file
    logging.info("Writing local meta-data file: %s"%mfile)
    config = cparser.ConfigParser()
    config.add_section("master")
    config.set('master', "hash", lcat_hash)
    utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)[:-4]
    config.set('master', "modification_utc", utcnow)
    with open(mfile, 'w') as f:
        config.write(f)


def read_meta_file(catalog):
    """Returns a dict of dict where the first dict represents
       sections and the second dict represents options"""

    mfile = catalog2meta_file(catalog)
    assert isfile(mfile)

    #Let's read the meta-data of the catalog file
    logging.info("Reading meta-data file: %s"%mfile)
    config = cparser.ConfigParser()
    config.read(mfile)

    if not config.has_section("master"):
        raise RuntimeError("The meta-data file '%s' has no master section"%mfile)

    ret = {}
    for sec in config.sections():
        ret[sec] = {}
        for (name, value) in config.items(sec):
            if value == "True":
                value = True
            elif value == "False":
                value = False

            try:# Try to convert the value to a time object
               t = datetime.strptime(value, DATETIME_FORMAT)
               value = t
            except ValueError:
                pass
            ret[sec][name] = value
    return ret


def meta_file_sanity(catalog):
    """Check the sanity of the meta-data associated the 'catalog' """

    meta = read_meta_file(catalog)
    lcat_hash1 = meta["master"]["hash"]
    lcat_hash2 = hashsum(catalog)
    if lcat_hash1 != lcat_hash2:
        raise RuntimeError("The hash in the meta-data file '%s' does not "\
                           "equal the hash of the catalog file '%s': %s != %s"\
                           %(catalog2meta_file(catalog), catalog, lcat_hash1, lcat_hash2))


def cmd_init_push_to_cloud(args):
    """Initiate the local catalog and push it the cloud"""

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)
    logging.info("[init-push-to-cloud]: %s => %s"%(lcat, ccat))

    if not isfile(lcat):
        args.error("[init-push-to-cloud] The local catalog does not exist: %s"%lcat)
    if isfile(ccat):
        args.error("[init-push-to-cloud] The cloud catalog already exist: %s"%ccat)

    (lmeta, cmeta) = (catalog2meta_file(lcat), catalog2meta_file(ccat))
    if isfile(lmeta):
        args.error("[init-push-to-cloud] The local meta-data already exist: %s"%lmeta)
    if isfile(cmeta):
        args.error("[init-push-to-cloud] The cloud meta-data already exist: %s"%cmeta)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Let's "lock" the cloud catalog
    logging.info("Locking cloud catalog: %s"%(ccat))
    if not lock_file(ccat):
        raise RuntimeError("The cloud catalog %s is locked!"%ccat)

    # Write meta-data both to local and cloud
    write_local_meta_file(args)
    logging.info("Copying local meta-data to cloud: %s => %s"%(lmeta, cmeta))
    shutil.copy2(lmeta, cmeta)

    #Copy catalog from local to cloud
    copy_catalog(lcat, ccat, local2cloud=True)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally,let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)
    logging.info("Unlocking cloud catalog: %s"%(ccat))
    unlock_file(ccat)

    logging.info("[init-push-to-cloud]: Success!")


def cmd_init_pull_from_cloud(args):
    """Initiate the local catalog by downloading the cloud catalog"""

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)
    logging.info("[init-pull-from-cloud]: %s => %s"%(ccat, lcat))

    if isfile(lcat):
        args.error("[init-pull-from-cloud] The local catalog already exist: %s"%lcat)
    if not isfile(ccat):
        args.error("[init-pull-from-cloud] The cloud catalog does not exist: %s"%ccat)

    (lmeta, cmeta) = (catalog2meta_file(lcat), catalog2meta_file(ccat))
    if isfile(lmeta):
        args.error("[init-pull-from-cloud] The local meta-data already exist: %s"%lmeta)
    if not isfile(cmeta):
        args.error("[init-pull-from-cloud] The cloud meta-data does not exist: %s"%cmeta)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Let's "lock" the cloud catalog
    logging.info("Locking cloud catalog: %s"%(ccat))
    if not lock_file(ccat):
        raise RuntimeError("The cloud catalog %s is locked!"%ccat)

    #Copy from cloud to local
    copy_catalog(lcat, ccat, local2cloud=False)
    logging.info("Copying cloud meta-data to local: %s => %s"%(cmeta, lmeta))
    shutil.copy2(cmeta, lmeta)
    meta_file_sanity(lcat)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=False)

    #Finally, let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)
    logging.info("Unlocking cloud catalog: %s"%(ccat))
    unlock_file(ccat)

    logging.info("[init-pull-from-cloud]: Success!")


def cmd_normal(args):
    """Normal procedure:
        * Pull from cloud (if necessary)
        * Run Lightroom
        * Push to cloud
    """

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)

    if not isfile(lcat):
        args.error("The local catalog does not exist: %s"%lcat)
    if not isfile(ccat):
        args.error("The cloud catalog does not exist: %s"%ccat)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Let's "lock" the cloud catalog
    logging.info("Locking cloud catalog: %s"%(ccat))
    if not lock_file(ccat):
        raise RuntimeError("The cloud catalog %s is locked!"%ccat)

    meta_file_sanity(lcat)
    ldict = read_meta_file(lcat)
    cdict = read_meta_file(ccat)

    if ldict['master']['hash'] != cdict['master']['hash']:
        logging.info("The local catalog needs updating")

        #Make sure we don't overwrite a modified local catalog
        if ldict['master']['modification_utc'] > cdict['master']['modification_utc']:
            raise RuntimeError("The local catalog is newer than the cloud catalog. "
                               "Please remove one of them: '%s' or '%s'"%(lcat,ccat))

        #Backup the local catalog (overwriting old backup)
        try:
            logging.info("Removed old backup: %s.backup"%lcat)
            os.remove("%s.backup"%lcat)
        except OSError:
            pass
        logging.info("Backup: %s => %s.backup"%(lcat, lcat))
        shutil.move(lcat, "%s.backup"%lcat)

        #Copy from cloud to local
        copy_catalog(lcat, ccat, local2cloud=False)
    else:
        logging.info("The local catalog is up to date")

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

    # Write meta-data both to local and cloud
    (lmeta, cmeta) = (catalog2meta_file(lcat), catalog2meta_file(ccat))
    write_local_meta_file(args)
    logging.info("Copying local meta-data to cloud: %s => %s"%(lmeta, cmeta))
    shutil.copy2(lmeta, cmeta)

    #Copy from local to cloud
    copy_catalog(lcat, ccat, local2cloud=True)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally, let's unlock the catalog files
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
        if p in ['init_push_to_cloud', 'init_pull_from_cloud', \
                 'verbose', 'config_file', 'error']:
            continue#We ignore some attributes
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

    cmd_group = parser.add_mutually_exclusive_group()
    cmd_group.add_argument(
        '--init-push-to-cloud',
        help='Initiate the local catalog and push it to the cloud',
        action="store_true"
    )
    cmd_group.add_argument(
        '--init-pull-from-cloud',
        help='Download the cloud catalog and initiate a corresponding local catalog',
        action="store_true"
    )
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
    args.error = parser.error

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    read_config_file(args)
    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)

    if lcat is None:
        parser.error("No local catalog specified, use --local-catalog")
    if ccat is None:
        parser.error("No cloud catalog specified, use --cloud-catalog")

    return args


if __name__ == "__main__":

    args = parse_arguments()
    try:
        if args.init_push_to_cloud:
            cmd_init_push_to_cloud(args)
        elif args.init_pull_from_cloud:
            cmd_init_pull_from_cloud(args)
        else:
            cmd_normal(args)
    finally:
        unlock_file(args.local_catalog)
        unlock_file(args.cloud_catalog)

    write_config_file(args)


