#!/usr/bin/env python
# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2013-2014 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import ConfigParser
import daemon
import extras

# as of python-daemon 1.6 it doesn't bundle pidlockfile anymore
# instead it depends on lockfile-0.9.1 which uses pidfile.
pid_file_module = extras.try_imports(['daemon.pidlockfile', 'daemon.pidfile'])

import logging
import logging.config
import os
import sys
import signal
import traceback

# No zuul imports here because they pull in paramiko which must not be
# imported until after the daemonization.
# https://github.com/paramiko/paramiko/issues/59
# Similar situation with gear and statsd.


def stack_dump_handler(signum, frame):
    signal.signal(signal.SIGUSR2, signal.SIG_IGN)
    log_str = ""
    for thread_id, stack_frame in sys._current_frames().items():
        log_str += "Thread: %s\n" % thread_id
        log_str += "".join(traceback.format_stack(stack_frame))
    log = logging.getLogger("zuul.stack_dump")
    log.debug(log_str)
    signal.signal(signal.SIGUSR2, stack_dump_handler)


class Merger(object):
    def __init__(self):
        self.args = None
        self.config = None

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description='Zuul merge worker.')
        parser.add_argument('-c', dest='config',
                            help='specify the config file')
        parser.add_argument('-d', dest='nodaemon', action='store_true',
                            help='do not run as a daemon')
        parser.add_argument('--version', dest='version', action='store_true',
                            help='show zuul version')
        self.args = parser.parse_args()

    def read_config(self):
        self.config = ConfigParser.ConfigParser()
        if self.args.config:
            locations = [self.args.config]
        else:
            locations = ['/etc/zuul/zuul.conf',
                         '~/zuul.conf']
        for fp in locations:
            if os.path.exists(os.path.expanduser(fp)):
                self.config.read(os.path.expanduser(fp))
                return
        raise Exception("Unable to locate config file in %s" % locations)

    def setup_logging(self, section, parameter):
        if self.config.has_option(section, parameter):
            fp = os.path.expanduser(self.config.get(section, parameter))
            if not os.path.exists(fp):
                raise Exception("Unable to read logging config file at %s" %
                                fp)
            logging.config.fileConfig(fp)
        else:
            logging.basicConfig(level=logging.DEBUG)

    def exit_handler(self, signum, frame):
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)
        self.merger.stop()
        self.merger.join()

    def main(self):
        # See comment at top of file about zuul imports
        import zuul.merger.server

        self.setup_logging('merger', 'log_config')

        self.merger = zuul.merger.server.MergeServer(self.config)
        self.merger.start()

        signal.signal(signal.SIGUSR1, self.exit_handler)
        signal.signal(signal.SIGUSR2, stack_dump_handler)
        while True:
            try:
                signal.pause()
            except KeyboardInterrupt:
                print "Ctrl + C: asking merger to exit nicely...\n"
                self.exit_handler(signal.SIGINT, None)


def main():
    server = Merger()
    server.parse_arguments()

    if server.args.version:
        from zuul.version import version_info as zuul_version_info
        print "Zuul version: %s" % zuul_version_info.version_string()
        sys.exit(0)

    server.read_config()

    if server.config.has_option('zuul', 'state_dir'):
        state_dir = os.path.expanduser(server.config.get('zuul', 'state_dir'))
    else:
        state_dir = '/var/lib/zuul'
    test_fn = os.path.join(state_dir, 'test')
    try:
        f = open(test_fn, 'w')
        f.close()
        os.unlink(test_fn)
    except Exception:
        print
        print "Unable to write to state directory: %s" % state_dir
        print
        raise

    if server.config.has_option('merger', 'pidfile'):
        pid_fn = os.path.expanduser(server.config.get('merger', 'pidfile'))
    else:
        pid_fn = '/var/run/zuul-merger/zuul-merger.pid'
    pid = pid_file_module.TimeoutPIDLockFile(pid_fn, 10)

    if server.args.nodaemon:
        server.main()
    else:
        with daemon.DaemonContext(pidfile=pid):
            server.main()


if __name__ == "__main__":
    sys.path.insert(0, '.')
    main()
