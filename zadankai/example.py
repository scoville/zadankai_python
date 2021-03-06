#!/usr/local/bin/python3

from zadankai.zk_wrap import run

json = {
    'companies': {
        'count': 4,
        'groups': [1, 2, 1, 2],
        'ratings': {
            'values': [
                [1, 3, 2, 4, 4, 0],
                [0, 1, 2, 0, 3, 4],
                [2, 2, 4, 4, 3, 1],
                [1, 1, 1, 4, 4, 0],
            ],
            'weight': 1,
        }
    },
    'students': {
        'count': 6,
        'ratings': {
            'values': [
                [0, 3, 4, 2],
                [2, 3, 2, 2],
                [1, 1, 3, 1],
                [4, 4, 4, 0],
                [1, 1, 4, 1],
                [3, 2, 4, 1],
            ],
            'weight': 1,
        }
    },
    'terms': {
        'count': 2
    },
    'weights': {
        'delta': {
            'ttl': 20,
            'var': 80,
            'obj': 60,
        },
        'satisfaction': {
            'ttl': 20,
            'var': 80,
            'obj': 40,
        },
    },
    'maxTimeout': 5,
}

print(run(json))
