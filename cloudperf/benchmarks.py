# This is a python file, defining benchmarks to run on each cloud instances.
# Each benchmark must have a unique name as the dictionary key, which should
# contain a dictionary for each benchmarks, with the following keys:
#   - `program`: the name of the benchmark program (informative, not used for execution)
#   - `name`: the verbose name of the benchmark
#   - `images`: another, architecture-name keyed dictionary, which defines a docker image
#               for each architecture
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
#   - `cpus`: if not specified, the command will be run once for each CPU, having
#             the actual number of CPUs in the `numcpu` variable. For a 8 CPU
#             machine it means 8 runs with `numcpu` being 1,2,3,4,5,6,7,8.
#             `cpus` can be a python list, eg: 'cpus': [1,2,4,8,16]
#   - `iterations`: the benchmark will be runned this many times (for each CPUs)
#                   in order to have more measure points. Default: 3.
#   - `score_aggregation`: this python function will be used to aggregating the
#                          scores from the above iterations. The scores will be
#                          passed as a list of floats. Default: max
#                          WARNING: as stated above, given (or all) iterations
#                          can return `None`, so the aggregation function must be
#                          able to cope with that.

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
