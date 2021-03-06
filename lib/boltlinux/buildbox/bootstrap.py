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

import collections
import os
import re
import shlex
import shutil
import subprocess
import tempfile

from boltlinux.buildbox.misc.paths import Paths
from boltlinux.buildbox.misc.platform import Platform
from boltlinux.buildbox.error import BBoxError

OPKG_CONFIG_TEMPLATE = """\
##############################################################################
# OPTIONS
##############################################################################

option cache_dir /.pkg-cache
option signature_type usign
option no_install_recommends
option force_removal_of_dependent_packages
option force_postinstall

{opt_check_sig}

##############################################################################
# FEEDS
##############################################################################

src/gz main {repo_base}/{release}/core/{arch}/{libc}/main
src/gz main-debug {repo_base}/{release}/core/{arch}/{libc}/main-debug
src/gz tools {repo_base}/{release}/core/{arch}/{libc}/tools/{host_arch}
src/gz tools-debug {repo_base}/{release}/core/{arch}/{libc}/tools-debug/{host_arch}

##############################################################################
# ARCHES
##############################################################################

arch {arch} 1
arch all 1
arch tools 1

##############################################################################
# INSTALL ROOT
##############################################################################

dest root /
"""  # noqa

ETC_TARGET_TEMPLATE = """\
TARGET_ID={target_id}
TARGET_MACHINE={machine}
TARGET_TYPE={target_type}
TOOLS_TYPE={host_arch}-tools-linux-musl
"""

class BBoxBootstrap:

    def __init__(self, release, arch, libc="musl", do_verify=True,
            cache_dir=None):
        self._release   = release
        self._arch      = arch
        self._libc      = libc
        self._do_verify = do_verify
        self._cache_dir = cache_dir or Paths.cache_dir()
    #end function

    def bootstrap(self, target_dir, specfile, force=False, **options):
        opt_check_sig = "option check_signature" if self._do_verify else ""

        context = {
            "release":
                self._release,
            "libc":
                self._libc,
            "arch":
                self._arch,
            "host_arch":
                Platform.uname("-m"),
            "target_id":
                os.path.basename(target_dir),
            "machine":
                self._arch,
            "target_type":
                Platform.target_for_machine(self._arch),
            "opt_check_sig":
                opt_check_sig,
            "repo_base":
                options.get("repo_base")
        }

        package_cache = os.path.join(
            Paths.cache_dir(), "bolt", "dists", self._release, self._arch,
                self._libc
        )

        if not os.path.exists(package_cache):
            os.makedirs(package_cache)

        package_cache_symlink = os.path.join(target_dir, ".pkg-cache")

        if not os.path.exists(package_cache_symlink):
            os.symlink(package_cache, package_cache_symlink)

        batches = self._read_package_spec(specfile)

        with tempfile.TemporaryDirectory(prefix="bbox-") as dirname:
            opkg_conf = os.path.join(dirname, "opkg.conf")

            with open(opkg_conf, "w+", encoding="utf-8") as f:
                f.write(OPKG_CONFIG_TEMPLATE.format(**context))

            self._prepare_target(opkg_conf, target_dir, batches, **context)
        #end with
    #end function

    # PRIVATE

    def _prepare_target(self, opkg_conf, target_dir, batches, **context):
        dirs_to_create = [
            "var",
            "run",
            "etc",
            "etc/opkg",
            "etc/opkg/usign",
            "tools",
            "tools/bin",
            "usr",
            "usr/bin",
        ]

        for dirname in dirs_to_create:
            os.makedirs(os.path.join(target_dir, dirname), exist_ok=True)

        self._copy_qemu(target_dir)

        etc_target = os.path.join(target_dir, "etc", "target")
        with open(etc_target, "w+", encoding="utf-8") as f:
            f.write(ETC_TARGET_TEMPLATE.format(**context))

        var_run_symlink = os.path.join(target_dir, "var", "run")
        if not os.path.exists(var_run_symlink):
            os.symlink("../run", var_run_symlink)

        # NOTE: important detail here...
        shutil.copy2(opkg_conf, os.path.join(target_dir, "etc", "opkg"))

        opkg_cmd = shlex.split(
            "opkg --conf '{}' --offline-root '{}' update".format(
                opkg_conf,
                target_dir
            )
        )

        try:
            subprocess.run(opkg_cmd, check=True)
        except subprocess.CalledProcessError:
            raise BBoxError("failed to update package index.")

        for mode, batch in batches:
            mode = "install" if mode == "+" else "remove"

            opkg_cmd = shlex.split(
                "opkg --conf '{}' --offline-root '{}' {} {}".format(
                    opkg_conf, target_dir, mode, " ".join(batch)
                )
            )

            try:
                subprocess.run(opkg_cmd, check=True)
            except subprocess.CalledProcessError:
                raise BBoxError("failed to install batch of packages.")
        #end for
    #end function

    def _copy_qemu(self, target_dir):
        qemu_user_static = ""

        prefix_map = collections.OrderedDict([
            ("aarch64",
                "qemu-aarch64-static"),
            ("arm",
                "qemu-arm-static"),
            ("mips64el",
                "qemu-mips64el-static"),
            ("mipsel",
                "qemu-mipsel-static"),
            ("powerpc64el",
                "qemu-ppc64le-static"),
            ("powerpc64le",
                "qemu-ppc64le-static"),
            ("ppc64le",
                "qemu-ppc64le-static"),
            ("powerpc",
                "qemu-ppc-static"),
            ("riscv64",
                "qemu-riscv64-static"),
            ("s390x",
                "qemu-s390x-static"),
        ])

        for prefix, qemu_binary in prefix_map.items():
            if self._arch.startswith(prefix):
                qemu_user_static = qemu_binary
                break

        if not qemu_user_static:
            return

        source_path = Platform.find_executable(qemu_user_static)
        if not source_path:
            raise BBoxError(
                'could not find QEMU executable "{}".'.format(qemu_user_static)
            )

        target_dir = os.path.dirname(
            os.path.join(target_dir, source_path.lstrip("/"))
        )
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        shutil.copy2(source_path, target_dir)
    #end function

    def _read_package_spec(self, specfile):
        if not os.path.exists(specfile):
            raise BBoxError(
                "package spec file '{}' not found.".format(specfile)
            )
        #end if

        batches = []
        active_batch = []
        active_mode = None

        if not os.path.isfile(specfile):
            raise BBoxError("'{}' is not a regular file.".format(specfile))

        with open(specfile, "r", encoding="utf-8") as f:
            lineno = 0

            for line in f:
                lineno += 1

                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                m = re.match(r"^(?P<mode>\+|-|=)\s*(?P<pkg>\S*)\s*$", line)

                if not m:
                    raise BBoxError(
                        "malformatted entry in '{}' on line '{}'."
                        .format(specfile, lineno)
                    )
                #end if

                mode = m.group("mode") or "+"

                if mode != active_mode:
                    if active_batch:
                        batches.append((active_mode, active_batch))
                        active_batch = []
                    #end if

                    active_mode = mode
                #end if

                if mode in ["+", "-"]:
                    pkg = m.group("pkg")

                    if not pkg:
                        raise BBoxError(
                            "malformatted entry in '{}' on line '{}'."
                            .format(specfile, lineno)
                        )
                    #end if

                    active_batch.append(pkg)
                #end if
            #end for
        #end with

        if active_batch:
            batches.append((active_mode, active_batch))

        return batches
    #end function

#end class
