#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
import os
import pwd
import socket
import urllib3

import jinja2

from vyos.config import Config
from vyos import ConfigError

config_file = r'/etc/salt/minion'

# Please be careful if you edit the template.
config_tmpl = """

### Autogenerated by salt-minion.py ###

##### Primary configuration settings #####
##########################################

# The hash_type is the hash to use when discovering the hash of a file on
# the master server. The default is sha256, but md5, sha1, sha224, sha384 and
# sha512 are also supported.
#
# WARNING: While md5 and sha1 are also supported, do not use them due to the
# high chance of possible collisions and thus security breach.
#
# Prior to changing this value, the master should be stopped and all Salt
# caches should be cleared.
hash_type: {{ hash_type }}

#####         Logging settings       #####
##########################################
# The location of the minion log file
# The minion log can be sent to a regular file, local path name, or network
# location. Remote logging works best when configured to use rsyslogd(8) (e.g.:
# ``file:///dev/log``), with rsyslogd(8) configured for network logging. The URI
# format is: <file|udp|tcp>://<host|socketpath>:<port-if-required>/<log-facility>
#log_file: /var/log/salt/minion
#log_file: file:///dev/log
#log_file: udp://loghost:10514
#
log_file: {{ log_file }}

# The level of messages to send to the console.
# One of 'garbage', 'trace', 'debug', info', 'warning', 'error', 'critical'.
#
# The following log levels are considered INSECURE and may log sensitive data:
# ['garbage', 'trace', 'debug']
#
# Default: 'warning'
log_level: {{ log_level }}

# Set the location of the salt master server, if the master server cannot be
# resolved, then the minion will fail to start.
master:
{% for host in master -%}
- {{ host }}
{% endfor %}

# The user to run salt
user: {{ user }}

# The directory to store the pki information in
pki_dir: /config/salt/pki/minion

# Explicitly declare the id for this minion to use, if left commented the id
# will be the hostname as returned by the python call: socket.getfqdn()
# Since salt uses detached ids it is possible to run multiple minions on the
# same machine but with different ids, this can be useful for salt compute
# clusters.
id: {{ salt_id }}


# The number of minutes between mine updates.
mine_interval: {{ mine_interval }}

verify_master_pubkey_sign: {{ verify_master_pubkey_sign }}
"""

default_config_data = {
    'hash_type': 'sha256',
    'log_file': '/var/log/salt/minion',
    'log_level': 'warning',
    'master' : 'salt',
    'user': 'minion',
    'salt_id': socket.gethostname(),
    'mine_interval': '60',
    'verify_master_pubkey_sign': 'false'
}

def get_config():
    salt = default_config_data
    conf = Config()
    if not conf.exists('service salt-minion'):
        return None
    else:
        conf.set_level('service salt-minion')

    if conf.exists('hash_type'):
        salt['hash_type'] = conf.return_value('hash_type')

    if conf.exists('log_file'):
        salt['log_file'] = conf.return_value('log_file')

    if conf.exists('log_level'):
        salt['log_level'] = conf.return_value('log_level')

    if conf.exists('master'):
        master = conf.return_values('master')
        salt['master'] = master

    if conf.exists('ID'):
        salt['salt_id'] = conf.return_value('ID')

    if conf.exists('user'):
        salt['user'] = conf.return_value('user')

    if conf.exists('mine_interval'):
        salt['mine_interval'] = conf.return_value('mine_interval')

    salt['master-key'] = None
    if conf.exists('master-key'):
        salt['master-key'] = conf.return_value('mine_interval')
        salt['verify_master_pubkey_sign'] = 'true'

    return salt

def generate(salt):
    paths = ['/etc/salt/','/var/run/salt','/opt/vyatta/etc/config/salt/'] 
    directory = '/opt/vyatta/etc/config/salt/pki/minion'
    uid = pwd.getpwnam(salt['user']).pw_uid
    http = urllib3.PoolManager()

    if salt is None:
        return None

    if not os.path.exists(directory):
        os.makedirs(directory)

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(salt)
    with open(config_file, 'w') as f:
        f.write(config_text)
    path = "/etc/salt/"  
    for path in paths:
      for root, dirs, files in os.walk(path):  
        for usgr in dirs:  
          os.chown(os.path.join(root, usgr), uid, 100)
        for usgr in files:
          os.chown(os.path.join(root, usgr), uid, 100)

    if not os.path.exists('/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub'):
        if not salt['master-key'] is None:
            r = http.request('GET', salt['master-key'], preload_content=False)
    
            with open('/opt/vyatta/etc/config/salt/pki/minion/master_sign.pub', 'wb') as out:
                while True:
                    data = r.read(chunk_size)
                    if not data:
                        break
                    out.write(data)
    
            r.release_conn()

    return None

def apply(salt):
    if salt is not None:
        os.system("sudo systemctl restart salt-minion")
    else:
        # Salt access is removed in the commit
        os.system("sudo systemctl stop salt-minion")
        os.unlink(config_file)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
