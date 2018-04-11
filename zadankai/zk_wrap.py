#!/usr/local/bin/python3

import json
from zadankai.zk import ZadankaiCSP


def run(json):
    zk_csp = ZadankaiCSP(json['companies'], json['students'], json['terms'])
    return json.dumps(zk_csp.solve(json['weights'], max_timeout=json['maxTimeout']))
