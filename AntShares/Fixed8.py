# -*- coding:utf-8 -*-
"""
Description:
    Fixed8
Usage:
    from AntShares.Fixed8 import Fixed8
"""

import os
import sys
from decimal import Decimal as D
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from AntShares.Helper import big_or_little

def sci_to_str(sciStr):
    '''科学计数法转换成字符串'''
    assert type('str')==type(sciStr),'invalid format'
    if 'E' not in sciStr:
        return sciStr
    s = '%.8f' % float(sciStr)
    while '0' == s[-1] and '.' in s:
        s = s[:-1]
    if '.' == s[-1]:
        s = s[:-1]
    return s

class Fixed8(float):
    """docstring for Fixed8"""
    def __init__(self, number):
        super(Fixed8,self).__init__(number)
        if isinstance(number, D):
            self.f = number
        else:
            self.f = D(str(number))

    def getData(self):
        hex_str = self.getDataFree()
        if len(hex_str) < 16:
            hex_str = hex_str + ''.join(['0' for i in xrange(16-len(hex_str))])
        return hex_str

    def getDataFree(self):
        hex_str = hex(int(self.f*D('100000000')))[2:]
        if len(hex_str)%2:
            hex_str = '0' + hex_str
        return big_or_little(hex_str)

    @staticmethod
    def getNumStr(fixed8_str):
        hex_str = big_or_little(fixed8_str)
        d = D(int('0x' + hex_str, 16))
        return sci_to_str(str(d/100000000))

if __name__ == "__main__":
    price = 1.001
    price2 = 2
    print Fixed8(price).getData()
    print Fixed8(price2).getData()
