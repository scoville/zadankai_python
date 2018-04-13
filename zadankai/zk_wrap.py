#!/usr/local/bin/python3

import json
from zadankai.zk_alt import ZadankaiCSP


def run(json_input):
    zk_csp = ZadankaiCSP(json_input['companies'], json_input['students'], json_input['terms'])
    result = zk_csp.solve(json_input['weights'], max_timeout=json_input['maxTimeout'])
    if result is not None:
        zk_csp.print_solution()
    return json.dumps(result)
