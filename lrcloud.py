#!/usr/bin/env python

import argparse
import os
import sys
import shutil
import subprocess
import logging
import distutils.dir_util
from os.path import join, basename, dirname, isfile, abspath
import traceback
import zipfile
from zipfile import ZIP_DEFLATED
import tempfile
import hashlib
from functools import partial
from datetime import datetime
import re
import pprint

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
                print tmpfile, dst
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
    elif dzip:
        with zipfile.ZipFile(dst, mode='w', compression=ZIP_DEFLATED) as z:
            z.write(src, arcname=basename(src))
    else:#None of them are zipped
        shutil.copy2(src, dst)


def hashsum(filename):
    """Return a hash of the file From <http://stackoverflow.com/a/7829658>"""

    with open(filename, mode='rb') as f:
        d = hashlib.sha1()
        for buf in iter(partial(f.read, 2**20), b''):
            d.update(buf)
    return d.hexdigest()


class MetaFile:
    """Representation of a meta-file"""

    def __init__(self, file_path):
        self.file_path = file_path
        config = cparser.ConfigParser()
        config.read(file_path)
        logging.info("Read meta-data file: %s"%file_path)
        self._data = {}
        for sec in config.sections():
            self._data[sec] = {}
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
                except TypeError:
                    pass
                self._data[sec][name] = value

    def __getitem__(self, section):
        if section not in self._data:
            self._data[section] = {}
        return self._data[section]

    def flush(self):
        logging.info("Writing meta-data file: %s"%self.file_path)
        config = cparser.ConfigParser()
        for (sec, options) in self._data.items():
            config.add_section(sec)
            for (name, value) in options.items():
                config.set(sec, name, str(value))
        with open(self.file_path, 'w') as f:
            config.write(f)

class Node:
    def __init__(self, mfile):
        self.mfile = mfile
        self.parents = []
        self.children = []
        self.hash = mfile['changeset']['hash'] # Shortcut
    def __repr__(self):
        parents = "["
        for parent in self.parents:
            parents += "%s, "%parent.hash
        parents += "]"
        children = "["
        for child in self.children:
            children += "%s, "%child.hash
        children += "]"
        return "{%s, parents: %s, children: %s}"%(self.hash, parents, children)

class ChangesetDAG:

    def _get_all_cloud_mfiles(self, cloud_catalog):
        ret = ["%s.lrcloud"%cloud_catalog]
        cloud_dir = dirname(cloud_catalog)
        for f in os.listdir(cloud_dir):
            f = abspath(join(cloud_dir, f))
            if not isfile(f):
                continue
            pattern = "%s_[0-9a-fA-F]+\.zip\.lrcloud"%cloud_catalog
            if re.search(pattern, f):
                ret.append(f)
        return ret

    def __init__(self, cloud_catalog):
        self.nodes = {}  # Hash to node instance
        self.leafs = []  # Leaf nodes
        self.root = None # The root node

        # Instantiate all nodes
        for mfile in self._get_all_cloud_mfiles(cloud_catalog):
            mfile = MetaFile(mfile) # File path to class instance
            chash = mfile['changeset']['hash']
            assert (chash not in self.nodes)
            self.nodes[chash] = Node(mfile)
        # Assign parents
        for node in self.nodes.values():
            if not node.mfile['changeset']['is_base']:
                node.parents.append(self.nodes[node.mfile['parent']['hash']])
                assert len(node.parents) == 1
        # Assign children
        for node in self.nodes.values():
            for parent in node.parents:
                self.nodes[parent.hash].children.append(node)
                assert len(self.nodes[parent.hash].children) == 1
        # Find leaf nodes
        for node in self.nodes.values():
            if len(node.children) == 0:
                self.leafs.append(node)
        # Find the root node, which is the base changeset
        for node in self.nodes.values():
            if node.mfile['changeset']['is_base']:
                assert self.root is None
                self.root = node

        assert len(self.leafs) <= 1
        assert self.root is not None

    def path(self, a_hash, b_hash):
        """Return nodes in the path between 'a' and 'b' going from
        parent to child NOT including 'a' """

        def _path(a, b):
            if a is b:
                return [a]
            else:
                assert len(a.children) == 1
                return [a] + _path(a.children[0], b)

        a = self.nodes[a_hash]
        b = self.nodes[b_hash]
        return _path(a, b)[1:]


def cmd_init_push_to_cloud(args):
    """Initiate the local catalog and push it the cloud"""

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)
    logging.info("[init-push-to-cloud]: %s => %s"%(lcat, ccat))

    if not isfile(lcat):
        args.error("[init-push-to-cloud] The local catalog does not exist: %s"%lcat)
    if isfile(ccat):
        args.error("[init-push-to-cloud] The cloud catalog already exist: %s"%ccat)

    (lmeta, cmeta) = ("%s.lrcloud"%lcat, "%s.lrcloud"%ccat)
    if isfile(lmeta):
        args.error("[init-push-to-cloud] The local meta-data already exist: %s"%lmeta)
    if isfile(cmeta):
        args.error("[init-push-to-cloud] The cloud meta-data already exist: %s"%cmeta)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Copy catalog from local to cloud, which becomes the new "base" changeset
    copy_catalog(lcat, ccat, local2cloud=True)

    # Write meta-data both to local and cloud
    mfile = MetaFile(lmeta)
    utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)[:-4]
    mfile['catalog']['hash'] = hashsum(lcat)
    mfile['catalog']['modification_utc'] = utcnow
    mfile['catalog']['filename'] = lcat
    mfile['last_push']['filename'] = ccat
    mfile['last_push']['hash'] = hashsum(lcat)
    mfile['last_push']['modification_utc'] = utcnow
    mfile.flush()
    mfile = MetaFile(cmeta)
    mfile['changeset']['is_base'] = True
    mfile['changeset']['hash'] = hashsum(lcat)
    mfile['changeset']['modification_utc'] = utcnow
    mfile['changeset']['filename'] = ccat
    mfile.flush()

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally,let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)

    logging.info("[init-push-to-cloud]: Success!")


def cmd_init_pull_from_cloud(args):
    """Initiate the local catalog by downloading the cloud catalog"""

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)
    logging.info("[init-pull-from-cloud]: %s => %s"%(ccat, lcat))

    if isfile(lcat):
        args.error("[init-pull-from-cloud] The local catalog already exist: %s"%lcat)
    if not isfile(ccat):
        args.error("[init-pull-from-cloud] The cloud catalog does not exist: %s"%ccat)

    (lmeta, cmeta) = ("%s.lrcloud"%lcat, "%s.lrcloud"%ccat)
    if isfile(lmeta):
        args.error("[init-pull-from-cloud] The local meta-data already exist: %s"%lmeta)
    if not isfile(cmeta):
        args.error("[init-pull-from-cloud] The cloud meta-data does not exist: %s"%cmeta)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Copy base from cloud to local
    copy_catalog(lcat, ccat, local2cloud=False)

    #Apply changesets
    cloudDAG = ChangesetDAG(ccat)
    path = cloudDAG.path(cloudDAG.root.hash, cloudDAG.leafs[0].hash)
    for node in path:
        try:
            os.remove("/tmp/tmp.patch")
        except OSError:
            pass
        copy_catalog(node.mfile['changeset']['filename'], "/tmp/tmp.patch", local2cloud=True)
        print "mv %s %s"%(lcat, "/tmp/tmp.lcat")
        shutil.move(lcat, "/tmp/tmp.lcat")

        cmd = args.patch_cmd.replace("$in1", "/tmp/tmp.lcat")\
                            .replace("$patch", "/tmp/tmp.patch")\
                            .replace("$out", lcat)
        logging.info("Patch: %s"%cmd)
        subprocess.call(cmd, shell=True)

    # Write meta-data both to local and cloud
    mfile = MetaFile(lmeta)
    utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)[:-4]
    mfile['catalog']['hash'] = hashsum(lcat)
    mfile['catalog']['modification_utc'] = utcnow
    mfile['catalog']['filename'] = lcat
    mfile['last_push']['filename'] = cloudDAG.leafs[0].mfile['changeset']['filename']
    mfile['last_push']['hash'] = cloudDAG.leafs[0].mfile['changeset']['hash']
    mfile['last_push']['modification_utc'] = cloudDAG.leafs[0].mfile['changeset']['modification_utc']
    mfile.flush()

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=False)

    #Finally, let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)

    logging.info("[init-pull-from-cloud]: Success!")


def cmd_normal(args):
    """Normal procedure:
        * Pull from cloud (if necessary)
        * Run Lightroom
        * Push to cloud
    """

    (lcat, ccat) = (args.local_catalog, args.cloud_catalog)
    (lmeta, cmeta) = ("%s.lrcloud"%lcat, "%s.lrcloud"%ccat)

    if not isfile(lcat):
        args.error("The local catalog does not exist: %s"%lcat)
    if not isfile(ccat):
        args.error("The cloud catalog does not exist: %s"%ccat)

    #Let's "lock" the local catalog
    logging.info("Locking local catalog: %s"%(lcat))
    if not lock_file(lcat):
        raise RuntimeError("The catalog %s is locked!"%lcat)

    #Backup the local catalog (overwriting old backup)
    try:
        logging.info("Removed old backup: %s.backup"%lcat)
        os.remove("%s.backup"%lcat)
    except OSError:
        pass
    logging.info("Backup: %s => %s.backup"%(lcat, lcat))
    shutil.copy(lcat, "%s.backup"%lcat)

    lmfile = MetaFile(lmeta)
    cmfile = MetaFile(cmeta)

    #Apply changesets
    cloudDAG = ChangesetDAG(ccat)
    path = cloudDAG.path(lmfile['last_push']['hash'], cloudDAG.leafs[0].hash)
    for node in path:
        try:
            os.remove("/tmp/tmp.patch")
        except OSError:
            pass
        copy_catalog(node.mfile['changeset']['filename'], "/tmp/tmp.patch", local2cloud=True)
        print "mv %s %s"%(lcat, "/tmp/tmp.lcat")
        shutil.move(lcat, "/tmp/tmp.lcat")

        cmd = args.patch_cmd.replace("$in1", "/tmp/tmp.lcat")\
                            .replace("$patch", "/tmp/tmp.patch")\
                            .replace("$out", lcat)
        logging.info("Patch: %s"%cmd)
        subprocess.call(cmd, shell=True)

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=False)

    #Backup the local catalog (overwriting old backup)
    try:
        logging.info("Removed old backup: %s.backup"%lcat)
        os.remove("%s.backup"%lcat)
    except OSError:
        pass
    logging.info("Backup: %s => %s.backup"%(lcat, lcat))
    shutil.copy(lcat, "%s.backup"%lcat)

    #Let's unlock the local catalog so that Lightroom can read it
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)

    #Now we can start Lightroom
    logging.info("Starting Lightroom: %s %s"%(args.lightroom_exec, lcat))
    if args.lightroom_exec is not None or True:
        #subprocess.call(args.lightroom_exec, lcat)
        subprocess.call("echo hej >> %s"%lcat, shell=True)
    logging.info("Lightroom exit")

    args.diff_cmd = args.diff_cmd.replace("$in1", "%s.backup"%lcat)\
                                 .replace("$in2", lcat)\
                                 .replace("$out", "/tmp/tmp.patch")
    logging.info("Diff: %s"%args.diff_cmd)
    subprocess.call(args.diff_cmd, shell=True)

    patch = "%s_%s.zip"%(ccat, hashsum("/tmp/tmp.patch"))
    copy_catalog("/tmp/tmp.patch", patch, local2cloud=True)

    # Write cloud meta-data
    mfile = MetaFile("%s.lrcloud"%patch)
    utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)[:-4]
    mfile['changeset']['is_base'] = False
    mfile['changeset']['hash'] = hashsum("/tmp/tmp.patch")
    mfile['changeset']['modification_utc'] = utcnow
    mfile['changeset']['filename'] = patch
    mfile['parent']['is_base']          = cloudDAG.leafs[0].mfile['changeset']['is_base']
    mfile['parent']['hash']             = cloudDAG.leafs[0].mfile['changeset']['hash']
    mfile['parent']['modification_utc'] = cloudDAG.leafs[0].mfile['changeset']['modification_utc']
    mfile['parent']['filename']         = cloudDAG.leafs[0].mfile['changeset']['filename']
    mfile.flush()

    # Write local meta-data
    mfile = MetaFile(lmeta)
    mfile['catalog']['hash'] = hashsum(lcat)
    mfile['catalog']['modification_utc'] = utcnow
    mfile['last_push']['filename'] = patch
    mfile['last_push']['hash'] = hashsum("/tmp/tmp.patch")
    mfile['last_push']['modification_utc'] = utcnow
    mfile.flush()

    #Let's copy Smart Previews
    if not args.no_smart_previews:
        copy_smart_previews(lcat, ccat, local2cloud=True)

    #Finally, let's unlock the catalog files
    logging.info("Unlocking local catalog: %s"%(lcat))
    unlock_file(lcat)


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
    parser.add_argument(
        '--diff-cmd',
        help="The command that given two files, $in1 and $in2, "
             "produces a diff file $out",
        type=str,
        #default="./jdiff -f $in1 $in2 $out"
        default="bsdiff $in1 $in2 $out"
    )
    parser.add_argument(
        '--patch-cmd',
        help="The command that given a file, $in1, and a path, "
             "$patch, produces a file $out",
        type=str,
        #default="./jptch $in1 $patch $out"
        default="bspatch $in1 $out $patch"
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

    write_config_file(args)


