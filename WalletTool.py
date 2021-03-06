#coding:utf8
import ecdsa
import pycoin
import hashlib
import binascii
from base58 import b58decode
from decimal import Decimal as D
from AntShares.Fixed8 import Fixed8
from AntShares.Helper import big_or_little
from AntShares.Network.RemoteNode import RemoteNode
from AntShares.IO.MemoryStream import MemoryStream
from AntShares.IO.BinaryWriter import BinaryWriter
from AntShares.Core.Transaction import Transaction
from AntShares.Core.TransactionInput import TransactionInput
from AntShares.Core.TransactionOutput import TransactionOutput
from AntShares.Cryptography.Helper import get_privkey_format,decode_privkey,encode_pubkey,fast_multiply,G,redeem_to_scripthash,bin_dbl_sha256,pubkey_to_redeem,redeem_to_scripthash,scripthash_to_address
from converttool import sci_to_str
from config import RPC_NODE,SERVER,PORT,NEP5_NODE
from random import randint


class WalletTool:
    @staticmethod
    def get_random_byte():
        '''
        获得单个16进制字符串
        '''
        return binascii.hexlify(chr(randint(0,255)))

    @classmethod
    def get_random_byte_str(cls, num):
        '''
        获得指定长度的16进制字符串
        '''
        return ''.join([cls.get_random_byte() for i in xrange(0,num)])

    @classmethod
    def transfer_nep5(cls,apphash,source,dest,value):
        '''
        构建NEP5代币转账InvocationTransaction
        '''
        s = 'd101'
        script = ''
        fa = Fixed8(value).getDataFree()
        faLen = hex(len(fa)/2)[2:]
        if 1 == len(faLen) % 2:
            faLen = '0' + faLen
        script += faLen + fa + '14' + cls.address_to_scripthash(dest) + '14' + cls.address_to_scripthash(source) + '53c1087472616e7366657267' + big_or_little(apphash) + 'f166' + cls.get_random_byte_str(8)
        scriptLen = hex(len(script)/2)[2:]
        if 1 == len(scriptLen) % 2:
            scriptLen = '0' + scriptLen
        s += scriptLen + script + '0000000000000000' + '0120' + cls.address_to_scripthash(source) + '0000'
        return s

    @classmethod
    def get_nep5_balance(cls, apphash, address):
        rn = RemoteNode('http://' + NEP5_NODE + ':10332')
        result = rn.getStorage(apphash, cls.address_to_scripthash(address))
        if result['result'] is None:
            return '0'
        else:
            return Fixed8.getNumStr(result['result'])

    @staticmethod
    def get_block_count(net):
        '''获取本地节点的高度'''
        assert net in ['testnet','mainnet'],'Wrong Net'
        port = 10332
        if 'testnet' == net:
            port = 20332
        rn = RemoteNode('http://%s:%s' % (RPC_NODE,port))
        return rn.getBlockCount()

    @staticmethod
    def get_last_height(net):
        '''从官方节点获取高度'''
        assert net in ['testnet','mainnet'],'Wrong Net'
        netPortDit = {'testnet':'20332','mainnet':'10332'}
        seeds = ['seed'+'%s' % i for i in range(1,6)]
        heights = []
        for seed in seeds:
            rn = RemoteNode('http://'+seed+'.neo.org:'+netPortDit[net])
            try:
                height = rn.getBlockCount()
            except:
                height = 0
            heights.append(height)
        print 'heights:%s' % heights
        return max(heights)

    @staticmethod
    def uncompress_pubkey(cpk):
        '''将压缩版公钥转换为完整版公钥'''
        from pycoin.ecdsa.numbertheory import modular_sqrt
        p = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
        a = -3
        b = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
        prefix = cpk[:2]
        x = int(cpk[2:],16)
        y_squared = (x**3 + a*x + b)%p
        y = modular_sqrt(y_squared, p)
        y_hex = '%x' % y
        if (1==int(y_hex[-1],16)%2 and '02' == prefix) or (0==int(y_hex[-1],16)%2 and '03' == prefix):
            y = p - y
        return '04%064x%064x' % (x,y)

    @staticmethod
    def address_to_scripthash(address):
        return binascii.hexlify(b58decode(address)[1:-4])

    @staticmethod
    def get_asset_balance(addressInfo, assetId):
        if addressInfo['balances'].has_key(assetId):
            return D(addressInfo['balances'][assetId])
        else:
            return D('0')
    
    @staticmethod
    def get_right_utxo(addressInfo, value, assetId):
        '''
        utxo选取原则:
            1.如果所有utxo相加后小于该金额,返回空
            2.排序
            3.如果存在正好等于该金额的,就取该utxo
            4.如果存在大于该金额的,就取大于该金额的最小的utxo
            5.取最大的utxo并移除,然后回到第3步以获取剩余金额的utxo
        '''
        result = []
        if not addressInfo['utxo'].has_key(assetId):
            return result
        if D(addressInfo['balances'][assetId]) < value:
            return result
        utxos = addressInfo['utxo'][assetId][:]
        for u in utxos:
            u['value'] = D(u['value'])
        sortedUtxos = sorted(utxos, cmp=lambda a,b:cmp(a['value'],b['value'])) #sort little --> big
        while value:
            if value in [s['value'] for s in sortedUtxos]:
                for s in sortedUtxos:
                    if value == s['value']:
                        result.append(s)
                        value = D('0')
                        break
            elif value < sortedUtxos[-1]['value']:
                for s in sortedUtxos:
                    if value < s['value']:
                        result.append(s)
                        value = D('0')
                        break
            else:
                result.append(sortedUtxos[-1])
                value = value - sortedUtxos[-1]['value']
                del sortedUtxos[-1]
        return result

    @classmethod
    def transfer(cls, addressInfo, items, assetId):
        '''生成交易输入与输出,输出为多方'''
        inputs = []
        outputs = []
        value = sum([i[1] for i in items])
        if not isinstance(value, D):
            value = D(str(value))
        rightUtxo = cls.get_right_utxo(addressInfo, value, assetId)
        assert rightUtxo
        for r in rightUtxo:
            inputs.append(TransactionInput(prevHash=r['prevHash'], prevIndex=r['prevIndex']))
        for i in items:
            outputs.append(TransactionOutput(AssetId=assetId,Value=i[1], ScriptHash=cls.address_to_scripthash(i[0])))
        returnValue = sum([D(i['value']) for i in rightUtxo]) - value
        if returnValue:
            outputs.append(TransactionOutput(AssetId=assetId,Value=returnValue, ScriptHash=cls.address_to_scripthash(addressInfo['_id'])))
        return inputs,outputs

    @staticmethod
    def pubkey_to_compress(pubkey):
        '''生成压缩版公钥'''
        assert 130==len(pubkey),'Wrong pubkey length'
        x,y = pubkey[2:66],pubkey[66:]
        prefix = '03' if int('0x'+y[-1],16)%2 else '02'
        return prefix + x

    @classmethod
    def pubkey_to_address(cls,pubkey):
        if 130 == len(pubkey):
            compressPubkey = cls.pubkey_to_compress(pubkey)
        else:
            assert 66==len(pubkey),'Wrong PublicKey Length'
            compressPubkey = pubkey
        redeem = pubkey_to_redeem(compressPubkey)
        scripthash = redeem_to_scripthash(redeem)
        address = scripthash_to_address(scripthash)
        return address

    @staticmethod
    def private_to_hex_publickey(prik):
        '''私钥转换成公钥(完整版)'''
        f = get_privkey_format(prik)
        privkey = decode_privkey(prik, f)
        pubk = fast_multiply(G, privkey)
        pubk = encode_pubkey(pubk, 'hex')
        return pubk

    @staticmethod
    def sign(privkey, message):
        '''用私钥生成对message的签名'''
        sk = ecdsa.SigningKey.from_string(binascii.unhexlify(privkey), curve=ecdsa.SECP256k1, hashfunc = hashlib.sha256)
        signature = binascii.hexlify(sk.sign(binascii.unhexlify(message), hashfunc=hashlib.sha256))
        return signature

    @staticmethod
    def verify(pubkey, message, signature):
        '''验证签名 pubkey:hex pubkey, not hex_compressed'''
        vk = ecdsa.VerifyingKey.from_string(binascii.unhexlify(pubkey[2:]), curve=ecdsa.SECP256k1, hashfunc = hashlib.sha256)
        try:
            return vk.verify(binascii.unhexlify(signature), binascii.unhexlify(message))
        except ecdsa.BadSignatureError:
            return False

    @staticmethod
    def generate_unsignature_transaction(inputs,outputs):
        '''获取未签名的交易和txid'''
        tx = Transaction(inputs, outputs, [])
        stream = MemoryStream()
        writer = BinaryWriter(stream)
        tx.serializeUnsigned(writer)
        reg_tx = stream.toArray()
        txid = tx.ensureHash()
        return reg_tx,txid

    @staticmethod
    def compute_txid(tran):
        '''计算txid'''
        return big_or_little(binascii.hexlify(bin_dbl_sha256(binascii.unhexlify(tran))))

    @classmethod
    def send_transaction_to_node(cls,regtx,tran,net,node=RPC_NODE):
        try:
            url = 'http://'+node+(':20332' if 'testnet'==net else ':10332')
            RN = RemoteNode(url)
            r = RN.sendRawTransaction(regtx)
            if r.has_key('error') and r['error']:
                #print '-'*5,'raw:',regtx
                return False,r['error']['message'] + 'regtx:%s' % regtx
            if r['result']:
                txid = cls.compute_txid(tran)
                #print '-'*5,'txid:',txid
                return True,txid
            else:
                #print '-'*5,'raw:',regtx
                return False, 'broadcast falure'
        except Exception as e:
            #print '*'*5,'Exception','*'*5,e
            return False,'Exception:%s' % e

    @staticmethod
    def get_length_for_tx(ins):
        assert len(ins)<65536,'Too much items'
        aoLenHex = hex(len(ins))[2:]
        aoLenHex = '0' + aoLenHex if len(aoLenHex)%2 else aoLenHex
        return big_or_little(aoLenHex)

    @staticmethod
    def compute_gas(height,claims,db):
        if not claims:
            claims = {}
        if claims.has_key('_id'):
            del claims['_id']
        decrementInterval = 2000000
        generationAmount = [8, 7, 6, 5, 4, 3, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] 
        available = unavailable = D('0')
        for k,v in claims.items():
            if 0 == v['stopIndex']:
                v['stopIndex'] = height
                v['status'] = False
            else:
                v['status'] = True
            amount = D('0')
            ustart = v['startIndex'] / decrementInterval
            if ustart < len(generationAmount):
                istart = v['startIndex'] % decrementInterval
                uend =   v['stopIndex'] / decrementInterval
                iend =   v['stopIndex'] % decrementInterval
                if uend >= len(generationAmount):
                    uend = len(generationAmount)
                    iend = 0
                if 0 == iend:
                    uend -= 1
                    iend = decrementInterval
                while ustart < uend:
                    amount += (decrementInterval - istart) * generationAmount[ustart]
                    ustart += 1
                    istart = 0
                assert ustart == uend,'error X'
                amount += (iend - istart) * generationAmount[ustart]
            if v['startIndex'] > 0:
                amount += D(db.blocks.find_one({'_id':v['stopIndex']-1})['sys_fee']) - D(db.blocks.find_one({'_id':v['startIndex']})['sys_fee'])
            else:
                amount += D(db.blocks.find_one({'_id':v['stopIndex']-1})['sys_fee'])
            if v['status']:
                available += D(v['value']) / 100000000 * amount
            else:
                unavailable += D(v['value']) / 100000000 * amount
        base = {'available':sci_to_str(str(available)),'unavailable':sci_to_str(str(unavailable))}
        base['claims'] = [i.split('_') for i in claims.keys() if claims[i]['stopHash']]
        return base

    @classmethod
    def claim_gas(cls,address,height,claims,db):
        details = cls.compute_gas(height,claims,db)
        if D(details['available']):
            tx = '0200' + cls.get_length_for_tx(details['claims'])
            for c in details['claims']:
                tx += big_or_little(c[0])
                prevIndex = cls.get_length_for_tx(int(c[1])*[0])
                if len(prevIndex) < 4:
                    prevIndex += '00'
                tx += prevIndex
            tx += '000001e72d286979ee6cb1b7e65dfddfb2e384100b8d148e7758de42e4168b71792c60'
            tx += Fixed8(details['available']).getData()
            tx += cls.address_to_scripthash(address)
            return tx,cls.compute_txid(tx)
        return False,'No Gas'
