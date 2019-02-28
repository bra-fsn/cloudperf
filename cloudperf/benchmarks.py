# This is a python file, defining benchmarks to run on each cloud instances.
# Each benchmark must have a unique name as the dictionary key, which should
# contain a dictionary for each benchmarks, with the following keys:
#   - `program`: the name of the benchmark program (informative, not used for execution)
#   - `name`: the verbose name of the benchmark
#   - `images`: another, architecture-name keyed dictionary, which defines a docker image
#               for each architecture
#   - `files`: a dictonary of file names and file contents (string) to write to
#              the host, like: {'setup_db.sh': crdb_setup},`
#   - `cmd`: the command to be passed to the docker image. Variable expansion
#            is available here with the following variables:
#               - `numcpu`: the excercised number of CPUs (if the benchmark can
#                           utilize more CPUs, it can be limited to that number).
#                           Without any other settings, the command will be invoked
#                           once for each CPUs, with an increasing number in `numcpu`
#            The variable expansion works by using `{numcpu}` in the command.
#            Due to this, `{}` must be escaped as `{{}}`.
#            The command must output a single number, parseable with python's
#            `float`, which will be the benchmark's score.
#            If the output can't be parsed with `float`, a `None` will be inserted,
#            so if the benchmark couldn't run on that instance (for example because
#            it doesn't have the needed amount of memory), we won't re-run the
#            benchmark forever, only after the expiration period is over.
#   - `timeout`: the cmd will be started with `timeout n`. This helps preventing a
#           stuck script to run forever.
#   - `cpus`: if not specified, the command will be run once for each CPU, having
#             the actual number of CPUs in the `numcpu` variable. For a 8 CPU
#             machine it means 8 runs with `numcpu` being 1,2,3,4,5,6,7,8.
#             `cpus` can be a python list, eg: 'cpus': [1,2,4,8,16]
#   - `iterations`: the benchmark will be runned this many times (for each CPUs)
#                   in order to have more measure points. Default: 3.
#   - `score_aggregation`: this python function will be used to aggregating the
#                          scores from the above iterations. The scores will be
#                          passed as a list of floats. Default: max

crdb_tag = 'v2.1.5'
stress_ng_tag = 'latest'

crdb_compose_yml = """version: '3'

services:
  db-0:
    image: cockroachdb/cockroach:{tag}
    command: start --insecure
    expose:
     - "8080"
     - "26257"
    ports:
     - "26257:26257"
     - "8080:8080"
    networks:
     - roachnet
    volumes:
     - ./data/db-0:/cockroach/cockroach-data
  db-1:
    image: cockroachdb/cockroach:{tag}
    command: start --insecure --join=db-0 --join=db-2
    networks:
     - roachnet
    volumes:
     - ./data/db-1:/cockroach/cockroach-data
  db-2:
    image: cockroachdb/cockroach:{tag}
    command: start --insecure --join=db-0 --join=db-1
    networks:
     - roachnet
    volumes:
     - ./data/db-2:/cockroach/cockroach-data
  # db-init:
  #  image: cockroachdb/cockroach:{tag}
  #  networks:
  #   - roachnet
  #  volumes:
  #    - ./setup_db.sh:/setup_db.sh
  #  entrypoint: "/bin/bash"
  #  command: /setup_db.sh
networks:
  roachnet:
""".format(tag=crdb_tag)

crdb_sysbench_common_opts = "--db-driver=pgsql --oltp-table-size=100000 --oltp-tables-count=24 " \
    "--pgsql-host=db-1 --pgsql-port=26257 --pgsql-user=root --pgsql-db=cloudperf"

crdb_compose_up = """#!/bin/sh
docker run --rm --network ec2-user_roachnet cockroachdb/cockroach:{} sql --host db-1 --insecure -e "CREATE DATABASE cloudperf;"
docker run --rm --network ec2-user_roachnet severalnines/sysbench sysbench --threads=1 {} /usr/share/sysbench/tests/include/oltp_legacy/parallel_prepare.lua prepare
""".format(crdb_tag, crdb_sysbench_common_opts)

crdb_compose_down = """#!/bin/sh
sudo rm -rf data
"""


mysql_compose_yml = """version: '3'

services:
  mysql:
    image: mysql/mysql-server:{}
    environment:
     - MYSQL_ROOT_PASSWORD=password
     - MYSQL_ROOT_HOST=%
    expose:
     - "3306"
    ports:
     - "3306:3306"
    networks:
     - mysql
    volumes:
     - ./data/mysql:/var/lib/mysql
networks:
  mysql:
"""

mysql_sysbench_common_opts = "--db-driver=mysql --oltp-table-size=100000 --oltp-tables-count=24 " \
    "--mysql-host=mysql --mysql-user=root --mysql-db=cloudperf"
mysql_compose_up = """#!/bin/sh
docker run --rm --network ec2-user_mysql mysql/mysql-server sh -c 'echo "create database cloudperf" | mysql -u root -ppassword -h mysql'
docker run --rm --network ec2-user_mysql severalnines/sysbench sysbench --threads=1 {} /usr/share/sysbench/tests/include/oltp_legacy/parallel_prepare.lua prepare
""".format(mysql_sysbench_common_opts)
mysql_compose_down = """#!/bin/sh
sudo rm -rf data
"""

benchmarks = {
    # 'sysbench:oltp:cockroachdb:{}'.format(crdb_tag): {'program': 'cockroachdb',
    #                                                   'name': 'stress-ng matrixprod',
    #                                                   'composefile': crdb_compose_yml,
    #                                                   'after_compose_up': crdb_compose_up,
    #                                                   'after_compose_down': crdb_compose_down,
    #                                                   # 'files': {'setup_db.sh': crdb_setup},
    #                                                   'docker_opts': '--network ec2-user_roachnet',
    #                                                   'cmd': "sysbench --threads={numcpu} " + crdb_sysbench_common_opts + " /usr/share/sysbench/tests/include/oltp_legacy/oltp.lua run | fgrep 'queries:' | egrep -o '[0-9.]+ per sec' | awk '{{print $1}}'",
    #                                                   'images': {'x86_64': 'severalnines/sysbench'}
    #                                                   },
    # 'sysbench:oltp:mysql:5.5': {'program': 'mysql',
    #                          'name': 'stress-ng matrixprod',
    #                          'composefile': mysql_compose_yml.format('5.5'),
    #                          'after_compose_up': mysql_compose_up,
    #                          'after_compose_down': mysql_compose_down,
    #                          # 'files': {'setup_db.sh': crdb_setup},
    #                          'docker_opts': '--network ec2-user_mysql',
    #                          'cmd': "sysbench --threads={numcpu} " + mysql_sysbench_common_opts + " /usr/share/sysbench/tests/include/oltp_legacy/oltp.lua run | fgrep 'queries:' | egrep -o '[0-9.]+ per sec' | awk '{{print $1}}'",
    #                          'images': {'x86_64': 'severalnines/sysbench'}
    #                          },
    # 'sysbench:cpu': {'program': 'sysbench',
    #                  'name': 'sysbench CPU performance test',
    #                          'cmd': "sysbench cpu --max-time=5 --num-threads={numcpu} run | fgrep 'events per second' | egrep -o '[0-9.]+'",
    #                          'images': {'x86_64': 'severalnines/sysbench'}
    #                  },
    'stress-ng:hdd_rndwr_512': {'program': 'stress-ng',
                                'name': 'Random RW 512 bytes O_DIRECT, O_DSYNC',
                                'cmd': "--hdd {numcpu} --hdd-opts direct,dsync,rd-rnd,wr-rnd --hdd-write-size 512 -t 5 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                                'cpus': [256],
                                'timeout': 10,
                                'images': {'x86_64': 'brafsn/stress-ng-x86_64:{}'.format(stress_ng_tag),
                                           'arm64': 'brafsn/stress-ng-arm64:{}'.format(stress_ng_tag)},
                                },
    'stress-ng:hdd_rndwr_4k': {'program': 'stress-ng',
                               'name': 'Random RW 4k O_DIRECT, O_DSYNC',
                               'cmd': "--hdd {numcpu} --hdd-opts direct,dsync,rd-rnd,wr-rnd --hdd-write-size 4k -t 5 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                               'cpus': [256],
                               'timeout': 10,
                               'images': {'x86_64': 'brafsn/stress-ng-x86_64:{}'.format(stress_ng_tag),
                                          'arm64': 'brafsn/stress-ng-arm64:{}'.format(stress_ng_tag)},
                               },
    'stress-ng:crc16': {'program': 'stress-ng',
                        'name': 'compute 1024 rounds of CCITT CRC16 on random data',
                        'cmd': "--cpu {numcpu} --cpu-method crc16 -t 5 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                        'timeout': 10,
                        'images': {'x86_64': 'brafsn/stress-ng-x86_64:{}'.format(stress_ng_tag),
                                   'arm64': 'brafsn/stress-ng-arm64:{}'.format(stress_ng_tag)},
                        },
    'stress-ng:matrixprod': {'program': 'stress-ng',
                             'name': 'matrix product of two 128 x 128 matrices of double floats',
                             'cmd': "--cpu {numcpu} --cpu-method matrixprod -t 5 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                             'timeout': 10,
                             'images': {'x86_64': 'brafsn/stress-ng-x86_64:{}'.format(stress_ng_tag),
                                        'arm64': 'brafsn/stress-ng-arm64:{}'.format(stress_ng_tag)},
                             }
}
