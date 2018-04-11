#!/usr/local/bin/python3

from zadankai.zk import ZadankaiCSP


def run(json):
    zk_csp = ZadankaiCSP(json['companies'], json['students'], json['terms'])
    return zk_csp.solve(json['weights'], max_timeout=json['maxTimeout'])
