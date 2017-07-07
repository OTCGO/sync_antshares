#! /usr/bin/env python
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import argparse
import gevent.monkey
gevent.monkey.patch_all()
from binascii import unhexlify
from AntShares.Network.RemoteNode import RemoteNode
from AntShares.Cryptography.Helper import pubkey_to_address,scripthash_to_address,redeem_to_scripthash
from pymongo.errors import DuplicateKeyError
from pymongo import MongoClient
from decimal import Decimal as D,ROUND_DOWN
from .converttool import sci_to_str
import datetime
import gevent
import time
import sys
GEVENT_MAX = 100
SYNC_TIME_GAP = 0.05
ANS = 'c56f33fc6ecfcd0c225c4ab356fee59390af8560be0e930faebe74a6daff7c9b'


def get_fixed_slice(arr, step):
    for i in xrange(0,len(arr),step):
        yield arr[i:i+step]

def verification_to_address(verification):
    if 70 == len(verification) and '21' == verification[:2] and 'ac' == verification[-2:]:
        return pubkey_to_address(verification[2:-2])
    else:
        return scripthash_to_address(redeem_to_scripthash(unhexlify(verification)))
    
def sync_claim(tr, index):
    if 'ClaimTransaction' == tr['type']:
        claims = tr['claims']
        addresses = map(verification_to_address,[i['verification'] for i in tr['scripts']])
        mongo_claims = []
        for a in addresses:
            ca = DB.claims.find_one({'_id':a})
            assert ca,'sync error: claim %s not exist %s' % (a,tr['txid'])
            mongo_claims.append(ca)
        for c in claims:
            startSign = c['txid'] + '_' + str(c['vout'])
            for mc in mongo_claims:
                if mc.has_key(startSign):
                    print '-'*5,a,'end',index,startSign
                    del mc[startSign]
                    break
            else:
                if index in [12203,12701,20503,26408,28775,30858,43452,53126,80287,83490,167260]:
                    print 'pass'
                else:
                    raise ValueError('sync error: claim not in database :%s' % startSign)
        for mc in mongo_claims:
            DB.claims.update({'_id':mc['_id']},mc)
        return
    for vi in tr['vin']:
        t = DB.transactions.find_one({'_id':vi['txid']})
        prevHash = vi['txid']
        prevIndex = vi['vout']
        asset = t['vout'][prevIndex]['asset']
        address = t['vout'][prevIndex]['address']
        if ANS == asset:
            mongo_claim = DB.claims.find_one({'_id':address})
            startSign = prevHash + '_' + str(prevIndex)
            assert mongo_claim, 'sync error: %s claim not exist' % address
            assert mongo_claim[startSign], 'sync error: %s not in %s claims' % (prevHash, address)
            mongo_claim[startSign]['stopIndex'] = index
            mongo_claim[startSign]['stopHash'] = tr['txid']
            DB.claims.update({'_id':address},mongo_claim)
    for i in xrange(len(tr['vout'])):
        vo = tr['vout'][i]
        address = vo['address']
        asset = vo['asset']
        value = vo['value']
        if ANS == asset:
            mongo_claim = DB.claims.find_one({'_id':address})
            if mongo_claim is None:
                mongo_claim = {'_id':address}
            startSign = tr['txid'] + '_' + str(vo['n'])
            mongo_claim[startSign] = {'startIndex':index,'value':value,'stopIndex':0,'stopHash':''}
            DB.claims.update({'_id':address},mongo_claim,True,False)
            print '+'*5,address,'start',index,value,startSign

def sync_address(tr):
    for vi in tr['vin']:
        t = DB.transactions.find_one({'_id':vi['txid']})
        prevHash = vi['txid']
        prevIndex = vi['vout']
        asset = t['vout'][prevIndex]['asset']
        address = t['vout'][prevIndex]['address']
        mongo_address = DB.addresses.find_one({'_id':address})
        for ux in mongo_address['utxo'][asset]:
            if prevHash == ux['prevHash'] and prevIndex == ux['prevIndex']:
                mongo_address['utxo'][asset].remove(ux)
                mongo_address['balances'][asset] = sci_to_str(str(D(mongo_address['balances'][asset])-D(ux['value'])))
                DB.addresses.update({'_id':address},mongo_address)
                print '-'*5,address,asset,mongo_address['balances'][asset],'-'*5
                break
    for i in xrange(len(tr['vout'])):
        vo = tr['vout'][i]
        append_element = {'prevHash':tr['txid'],'prevIndex':i,'value':vo['value']}
        mongo_address = DB.addresses.find_one({'_id':vo['address']})
        if mongo_address is not None and mongo_address.has_key('utxo') and mongo_address['utxo'].has_key(vo['asset']) and append_element in mongo_address['utxo'][vo['asset']]:
            continue
        if mongo_address is None:
            mongo_address = {'_id':vo['address'],
                        'balances':{},
                        'utxo':{}
                    }
        if vo['asset'] not in mongo_address['balances'].keys():
            mongo_address['balances'][vo['asset']] = '0'
        mongo_address['balances'][vo['asset']] = str(D(mongo_address['balances'][vo['asset']])+D(vo['value']))
        if not mongo_address['utxo'].has_key(vo['asset']):
            mongo_address['utxo'][vo['asset']] = []
        mongo_address['utxo'][vo['asset']].append(append_element)
        DB.addresses.update({'_id':vo['address']},mongo_address,True,False)
        print '+'*5,vo['address'],vo['asset'],mongo_address['balances'][vo['asset']],'+'*5

def sync_transaction(tr):
    _id = tr['txid']
    tr['_id'] = _id
    try:
        DB.transactions.insert_one(tr)
    except DuplicateKeyError:
        print 'duplicate transaction %s' % _id

def sync_block(num):
    start_time = time.time()
    while True:
        current_block = RN.getBlock(num)
        if not current_block.has_key('result'):
            time.sleep(SYNC_TIME_GAP)
        else:
            break
    mongo_block = {}
    mongo_block['_id'] = num
    mongo_block['previousblockhash'] = current_block['result']['previousblockhash']
    mongo_block['index'] = current_block['result']['index']
    mongo_block['hash'] = current_block['result']['hash']
    mongo_block['time'] = current_block['result']['time']
    trs = current_block['result']['tx']
    mongo_block['tx'] = []
    #sync address
    for tr in trs:
        sync_address(tr)
    #sync claim
    for tr in trs:
        sync_claim(tr, num)
    #sync transactions
    sys_fee = D('0')
    for i in get_fixed_slice(trs, GEVENT_MAX):
        threads = []
        for j in i:
            sys_fee += D(j['sys_fee']).quantize(D('1'),rounding=ROUND_DOWN)
            mongo_block['tx'].append(j['txid'])
            threads.append(gevent.spawn(sync_transaction, j))
        gevent.joinall(threads)
        if num:
            mongo_block['sys_fee'] = str(sys_fee + D(DB.blocks.find_one({'_id':num-1})['sys_fee']))
        else:
            mongo_block['sys_fee'] = str(sys_fee)
    try:
        result = DB.blocks.insert_one(mongo_block)
        print '->', num, 'at %f seconds, %s' % (time.time() - start_time, datetime.datetime.now())
    except DuplicateKeyError:
        print 'duplicate block %s' % num

def sync():
    while True:
        current_height = RN.getBlockCount()
        print 'current_height',current_height
        blocks_num = DB.blocks.count()
        if blocks_num <= current_height:
            for i in xrange(blocks_num, current_height+1):
                sync_block(i)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--db", default='antshares', help="verify database name, default antshares")
        parser.add_argument("-n", "--node", default='http://127.0.0.1:20332', help="remote node to sync blockchain data,default http://127.0.0.1:20332")
        parser.add_argument("-m", "--mongodb", default='127.0.0.1:27017', help="mongodb for store data,default 127.0.0.1:27017")
        args = parser.parse_args()
        RN = RemoteNode(args.node)
        MC = MongoClient('mongodb://' + args.mongodb + '/')
        DB = MC[args.db]
        sync()
    except Exception as e:
        print e
        sys.exit()
