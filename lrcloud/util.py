# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import shutil
import zipfile
from zipfile import ZIP_DEFLATED
from os.path import join, basename, dirname, isfile, abspath
import tempfile
import logging
import os
import subprocess

def copy(src, dst):
    """File copy that support compress and decompress of zip files"""

    (szip, dzip) = (src.endswith(".zip"), dst.endswith(".zip"))
    logging.info("Copy: %s => %s"%(src, dst))

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

def remove(path):
    """Remove file or dir if exist"""
    try:
        if isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass

def apply_changesets(args, changesets, catalog):
    """Apply the 'catalog' the changesets in the metafile list 'changesets'"""

    for node in changesets:
        remove("/tmp/tmp.patch")
        copy(node.mfile['changeset']['filename'], "/tmp/tmp.patch")
        logging.info("mv %s %s"%(catalog, "/tmp/tmp.lcat"))
        shutil.move(catalog, "/tmp/tmp.lcat")

        cmd = args.patch_cmd.replace("$in1", "/tmp/tmp.lcat")\
                            .replace("$patch", "/tmp/tmp.patch")\
                            .replace("$out", catalog)
        logging.info("Patch: %s"%cmd)
        subprocess.check_call(cmd, shell=True)
