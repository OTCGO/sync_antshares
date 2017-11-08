# -*- coding:utf-8 -*-
"""
Description:
    Account class in AntShares.Wallets
Usage:
    from AntShares.Wallets.Account import Account
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import binascii


from AntShares.Cryptography.Helper import *


class Account(object):
    """docstring for Account"""
    def __init__(self, privateKey=None):
        super(Account, self).__init__()
        if privateKey == None or len(binascii.unhexlify(privateKey)) != 32:
            self.privateKey = random_to_priv(random_key())
        else:
            self.privateKey = privateKey

        self.publicKey = privkey_to_pubkey(self.privateKey)
        redeemScript = pubkey_to_redeem(self.publicKey)
        self.scriptHash = redeem_to_scripthash(redeemScript)
        self.address = scripthash_to_address(self.scriptHash)

def __test():
    privKey = 'e54aa6d215a97b398f7124aae578f715a6549a40b312d717c7123360832c2387'
    acc = Account(privateKey=privKey)
    print acc.publicKey
    print acc.privateKey
    print acc.address
    print acc.scriptHash


if __name__ == '__main__':
    __test()
