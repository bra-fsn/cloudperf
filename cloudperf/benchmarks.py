# This is a python file, defining benchmarks to run on each cloud instances.
# Images specify the docker images to run (keyed by the CPU architecture),
# cmd is the command which is given to docker run.
# The command should output a single number, which can be parsed with python's
# `float`. It will be the benchmark's score.
# If there is no `cpus` option is given to the benchmark, the command will be run
# once for each CPU. So if the machine has 8 CPUs, this means 8 times.
# The actual number of CPUs is available in the {numcpu} variable, which will
# be 1, 2, 3, 4, 5, 6, 7, 8 in this case.
# `cpus` can be a list, for eg.: 'cpus': [1, 2, 4, 8, 16]

benchmarks = {
    'sng_matrixprod': {'program': 'stress-ng',
                       'name': 'stress-ng matrixprod',
                       # due to python formatting {} must be escaped by {{}}
                       'cmd': "--cpu {numcpu} --cpu-method matrixprod -t 10 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                       'images': {'x86_64': 'brafsn/stress-ng-x86_64',
                                  'arm64': 'brafsn/stress-ng-arm64'}
                       },
    'sng_zlib': {'program': 'stress-ng',
                 'name': 'stress-ng zlib',
                 'cmd': "--zlib {numcpu} --zlib-method fixed -t 10 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                 'images': {'x86_64': 'brafsn/stress-ng-x86_64',
                            'arm64': 'brafsn/stress-ng-arm64'}
                 }
}
