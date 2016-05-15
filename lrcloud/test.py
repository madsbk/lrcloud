# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest
import tempfile
from os.path import join, basename, dirname, isfile, abspath
import shutil
import sys

from . import __main__ as lrcloud
from .metafile import MetaFile

def cmd_init_push_to_cloud(local_catalog, cloud_catalog):
    args = [
            "--config-file=None",
            "--init-push-to-cloud",
            "--local-catalog=%s"%local_catalog,
            "--cloud-catalog=%s"%cloud_catalog,
           ]
    lrcloud.main(args)

def cmd_init_pull_from_cloud(local_catalog, cloud_catalog):
    args = [
            "--config-file=None",
            "--init-pull-from-cloud",
            "--local-catalog=%s"%local_catalog,
            "--cloud-catalog=%s"%cloud_catalog,
           ]
    lrcloud.main(args)

def cmd_update(local_catalog, cloud_catalog, write_data="hej"):
    args = ["-v",
            "--config-file", "None",
            "--local-catalog", local_catalog,
            "--cloud-catalog", cloud_catalog,
            "--lightroom-exec-debug",write_data,
           ]
    lrcloud.main(args)



class InitPush(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ccat = join(self.tmpdir, "cloud.zip")

        # Catalog #1
        self.lcat1 = join(self.tmpdir, "local1.lrcat")
        with open(self.lcat1, mode='w') as f:
            f.write("Init Lightroom Catalog\n")
        cmd_init_push_to_cloud(self.lcat1,  self.ccat)

    def tearDown(self):
        pass

    def check_catalog(self, catalog, changed_by=[]):
        with open(catalog, mode='r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1+len(changed_by))
            self.assertEqual(lines[0], "Init Lightroom Catalog\n")
            for i, line in enumerate(lines[1:]):
                self.assertEqual(line, "I am #%d\n"%changed_by[i])

    def testSingleUser(self):
        self.check_catalog(self.lcat1)
        cmd_update(self.lcat1, self.ccat, "I am #1")
        self.check_catalog(self.lcat1, [1])

    def testTwoUsers(self):
        cmd_update(self.lcat1, self.ccat, "I am #1")
        self.check_catalog(self.lcat1, [1])

        lcat2 = join(self.tmpdir, "local2.lrcat")
        cmd_init_pull_from_cloud(lcat2, self.ccat)
        self.check_catalog(lcat2, [1])

        cmd_update(lcat2, self.ccat, "I am #2")
        self.check_catalog(lcat2, [1,2])

        cmd_update(self.lcat1, self.ccat, "I am #1")
        self.check_catalog(self.lcat1, [1,2,1])




def main():
    unittest.main()

if __name__ == '__main__':
    main()
