benchmarks = {
    'matrixprod': {'program': 'stress-ng',
                   'name': 'stress-ng matrixprod',
                   # due to python formatting {} must be escaped by {{}}
                   'cmd': "--cpu {numcpu} --cpu-method matrixprod -t 10 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
                   #'cmd': "--cpu {numcpu} --cpu-method matrixprod -t 10 --metrics",
                   'images': {'x86_64': 'brafsn/stress-ng-x86_64',
                              'arm64': 'brafsn/stress-ng-arm64'}
                   },
    # 'zlib': {'program': 'stress-ng',
    #          'name': 'stress-ng zlib',
    #          'cmd': "--zlib {numcpu} --zlib-method fixed -t 10 --metrics 2>&1 | tail -1 | awk '{{print $9}}'",
    #          'images': {'x86_64': 'brafsn/stress-ng-x86_64',
    #                     'arm64': 'brafsn/stress-ng-arm64'}
    #          }
}
