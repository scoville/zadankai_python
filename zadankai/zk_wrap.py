#!/usr/local/bin/python3

import json
from zadankai.zk import ZadankaiCSP


def run(json_input):
    zk_csp = ZadankaiCSP(json_input['companies'], json_input['students'], json_input['terms'])
    return json.dumps(zk_csp.solve(json_input['weights'], max_timeout=json_input['maxTimeout']))
