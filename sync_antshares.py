#! /usr/bin/env python
# coding: utf-8
# flow@蓝鲸淘
# Licensed under the MIT License.

import argparse
import gevent.monkey
gevent.monkey.patch_all()
from AntShares.Network.RemoteNode import RemoteNode
from pymongo import MongoClient
from decimal import Decimal as D
import gevent
import time
GEVENT_MAX = 100
SYNC_TIME_GAP = 0.05


def get_fixed_slice(arr, step):
    for i in xrange(0,len(arr),step):
        yield arr[i:i+step]
    
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
                mongo_address['balances'][asset] = str(D(mongo_address['balances'][asset])-D(ux['value']))
                DB.addresses.update({'_id':address},mongo_address)
                print '-----',address,asset,mongo_address['balances'][asset],'-----'
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
        print '+++++',vo['address'],vo['asset'],mongo_address['balances'][vo['asset']],'+++++'

def sync_transaction(tr):
    _id = tr['txid']
    tr['_id'] = _id
    DB.transactions.update({'_id':_id},tr,True,False)

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
    mongo_block['height'] = current_block['result']['height']
    mongo_block['hash'] = current_block['result']['hash']
    mongo_block['time'] = current_block['result']['time']
    trs = current_block['result']['tx']
    mongo_block['tx'] = []
    #sync address and transaction
    for i in get_fixed_slice(trs, GEVENT_MAX):
        threads = []
        for j in i:
            mongo_block['tx'].append(j['txid'])
            threads.append(gevent.spawn(sync_address, j))
            threads.append(gevent.spawn(sync_transaction, j))
        gevent.joinall(threads)
    DB.blocks.update({'_id':num},mongo_block,upsert=True)
    print '->', num, 'at %f seconds' % (time.time() - start_time)

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
