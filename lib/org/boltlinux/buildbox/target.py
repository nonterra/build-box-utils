# -*- encoding: utf-8 -*-
#
# The MIT License (MIT)
#
# Copyright (c) 2019 Tobias Koch <tobias.koch@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import os
import re
import shlex
import subprocess
import shutil

from org.boltlinux.buildbox.utils import homedir
from org.boltlinux.buildbox.bootstrap import BBoxBootstrap
from org.boltlinux.buildbox.error import BBoxError

class BBoxTarget:

    @classmethod
    def create(cls, target_name, target_spec, **options):
        target_prefix = options.get(
            "target_prefix", BBoxTarget.target_prefix()
        )
        if not os.path.isdir(target_prefix):
            os.makedirs(target_prefix)

        target_dir = os.path.join(target_prefix, target_name)
        if os.path.exists(target_dir):
            if os.listdir(target_dir):
                if not options.get("force"):
                    raise BBoxError(
                        "found non-empty target directory at '{}', aborting."
                        .format(target_dir)
                    )
                #end if
            #end if
        else:
            os.makedirs(target_dir)

        dev_dir = os.path.join(target_dir, "dev")
        if not os.path.exists(dev_dir):
            os.makedirs(dev_dir)

        mount_cmd = shlex.split(
            "/usr/bin/build-box mount -m dev -t '{}' .".format(target_dir)
        )

        proc = subprocess.run(mount_cmd)
        if proc.returncode != 0:
            raise BBoxError("failed to bind mount /dev.")

        bootstrapper = BBoxBootstrap(
            options.get("release", "stable"),
            options.get("arch", "x86_64"),
        )

        bootstrapper.bootstrap(
            target_dir, target_spec, **options
        )
    #end function

    @classmethod
    def list(cls, **options):
        target_prefix = options.get(
            "target_prefix", BBoxTarget.target_prefix()
        )
        if not os.path.isdir(target_prefix):
            return

        for entry in os.listdir(target_prefix):
            machine = "unknown"

            if not os.path.isdir(os.path.join(target_prefix, entry)):
                continue

            shell_found = False

            for prefix in ["usr", "tools"]:
                shell = os.path.join(target_prefix, entry, prefix, "bin", "sh")
                if os.path.exists(shell):
                    shell_found = True
                    break
            #end for

            if not shell_found:
                machine = "defunct"

            etc_target = os.path.join(target_prefix, entry, "etc", "target")
            if not os.path.exists(etc_target):
                machine = "defunct"

            if machine != "defunct":
                with open(etc_target, "r", encoding="utf-8") as f:
                    for line in f:
                        m = re.match(
                            r"^TARGET_MACHINE\s*=\s*(?P<machine>\S+)\s*$", line
                        )
                        if not m:
                            continue
                        machine = m.group("machine")
                    #end for
                #end with
            #end if

            print("{} ({})".format(entry, machine))
        #end for
    #end function

    @classmethod
    def delete(self, target_name, **options):
        target_prefix = options.get(
            "target_prefix", BBoxTarget.target_prefix()
        )

        target_dir = os.path.normpath(
            os.path.join(target_prefix, target_name)
        )
        if not os.path.isdir(target_dir):
            raise BBoxError("target '{}' not found.".format(target_name))

        umount_cmd = shlex.split(
            "/usr/bin/build-box umount -t '{}' .".format(target_dir)
        )

        proc = subprocess.run(umount_cmd)
        if proc.returncode != 0:
            raise BBoxError("failed to remove bind mounts.")

        for subdir in ["dev", "proc", "sys", "home"]:
            full_path = os.path.join(target_dir, subdir)
            if os.path.exists(full_path) and os.listdir(full_path):
                raise BBoxError(
                    "the '{}' subdirectory is not empty, aborting."
                    .format(subdir)
                )
            #end if
        #end for

        with open("/proc/mounts", "r", encoding="utf-8") as f:
            buf = f.read()

        for line in buf.splitlines():
            _, mountpoint, _, _, _, _ = line.strip().split()

            mountpoint = os.path.normpath(os.path.realpath(mountpoint))
            if mountpoint.startswith(target_dir + os.sep):
                raise BBoxError(
                    "there is something mounted at '{}', aborting."
                    .format(mountpoint)
                )
            #end if
        #end for

        shutil.rmtree(target_dir)
    #end function

    @classmethod
    def target_prefix(cls):
        return os.path.join(homedir(), ".bolt", "targets")

#end class