#coding:utf8
import ecdsa
import hashlib
import binascii
from base58 import b58decode
from decimal import Decimal as D
from AntShares.Helper import big_or_little
from AntShares.Network.RemoteNode import RemoteNode
from AntShares.IO.MemoryStream import MemoryStream
from AntShares.IO.BinaryWriter import BinaryWriter
from AntShares.Core.Transaction import Transaction
from AntShares.Core.TransactionInput import TransactionInput
from AntShares.Core.TransactionOutput import TransactionOutput
from AntShares.Cryptography.Helper import get_privkey_format,decode_privkey,encode_pubkey,fast_multiply,G,redeem_to_scripthash,bin_dbl_sha256
from config import RPC_NODE,SERVER,PORT


class WalletTool:
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