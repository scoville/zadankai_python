#!/usr/local/bin/python3

import random
from zadankai.zk_wrap import run

num_companies = 6
num_students = 80
num_terms = 5

min_group_size = 1
max_group_size = 2

ratings_c_to_s = [
    [random.choice(range(0, 5)) for _ in range(num_students)]
    for _ in range(num_companies)
]
ratings_s_to_c = [
    [random.choice(range(0, 5)) for _ in range(num_companies)]
    for _ in range(num_students)
]

num_groups_per_company = [
    random.choice(range(min_group_size, max_group_size + 1))
    for _ in range(num_companies)
]

json = {
    'companies': {
        'count': num_companies,
        'groups': num_groups_per_company,
        'ratings': {
            'values': ratings_c_to_s,
            'weight': 1,
        }
    },
    'students': {
        'count': num_students,
        'ratings': {
            'values': ratings_s_to_c,
            'weight': 1,
        }
    },
    'terms': {
        'count': num_terms
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
    'maxTimeout': 20,
}

print(run(json))
