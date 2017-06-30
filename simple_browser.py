#coding:utf8
import tornado.ioloop
import tornado.web
from pymongo import MongoClient
import json
from datetime import datetime
from decimal import Decimal as D
from WalletTool import WalletTool as WT
from config import PORT

MC = MongoClient('mongodb://127.0.0.1:27017', maxPoolSize=50)


class CORSHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

class MainHandler(CORSHandler):
    def get(self):
        self.write("""<h1>Simple AntShares BlockChain Browser!</h1>
                    <ul>
                        <li><strong>GET</strong> /{net}/height</li>
                        <li><strong>GET</strong> /{net}/block/{block}</li>
                        <li><strong>GET</strong> /{net}/transaction/{txid}</li>
                        <li><strong>GET</strong> /{net}/claim/{address}</li>
                        <li><strong>GET</strong> /{net}/address/{address}</li>
                        <li><strong>POST</strong> /{net}/transfer</li>
                        <li><strong>POST</strong> /{net}/gas</li>
                        <li><strong>POST</strong> /{net}/broadcast</li>
                    </ul>
                    <br>
                    <br>
                    <h2>Links</h2>
                    <ul>
                        <li><a href='http://note.youdao.com/noteshare?id=b60cc93fa8e8804394ade199c52d6274'>如何转账</a></li>
                        <li><a href='http://note.youdao.com/noteshare?id=c2b09b4fa26d59898a0f968ccd1652a0'>如何提取ANC/NeoGas</a></li>
                        <li><a href='https://github.com/OTCGO/sync_antshares'>源代码</a></li>
                    </ul>
                    """)

class BrowserHandler(CORSHandler):
    def get(self,xid):
        print '%s %s' % (datetime.now(),self.request.path),
        db,table = self.request.path.split('/')[1:3]
        if 'block' == table:
            xid = int(xid)
        dbTable = MC[db][table+'s'] if table!='address' else MC[db][table+'es']
        result = dbTable.find_one({'_id':xid})
        if result and 'claim' == table:
            db = MC[db]
            height = db.blocks.count()
            result = WT.compute_gas(height,result,db)
        if result:
            print 'True'
            self.write(json.dumps(result))
        else:
            print 'False'
            self.write(json.dumps({}))

class HeightHandler(CORSHandler):
    def get(self):
        db = MC[self.request.path.split('/')[1]]
        h = db.blocks.count()
        print '%s %s' % (datetime.now(),self.request.path),'True'
        self.write(json.dumps({'height':h}))

class TransferHandler(CORSHandler):
    def post(self):
        print '%s %s' % (datetime.now(),self.request.path),
        db =        self.request.path.split('/')[1]
        source =    self.get_argument('source')
        assetId =   self.get_argument('assetId')
        dests =     self.get_argument('dests').split(',')
        amounts =   self.get_argument('amounts').split(',')
        amounts = [D(a) for a in amounts]
        if len(dests) != len(amounts):
            msg = 'dests length must be equal to amounts length'
            print 'False',msg
            self.write(json.dumps({'result':False,'error':msg}))
        else:
            items = zip(dests,amounts)
            addressInfo = MC[db]['addresses'].find_one({'_id':source})
            if not addressInfo:
                msg = 'invalid source'
                print 'False',msg
                self.write(json.dumps({'result':False,'error':msg}))
            else:
                if sum(amounts) > WT.get_asset_balance(addressInfo, assetId):
                    msg = 'poor balance'
                    print 'False',msg
                    self.write(json.dumps({'result':False,'error':msg}))
                else:
                    inputs,outputs = WT.transfer(addressInfo, items, assetId)
                    trans,txid = WT.generate_unsignature_transaction(inputs, outputs)
                    print 'True'
                    self.write(json.dumps({'result':True, 'transaction':trans}))

class GasHandler(CORSHandler):
    def post(self):
        print '%s %s' % (datetime.now(),self.request.path),
        db = MC[self.request.path.split('/')[1]]
        h = db.blocks.count()
        publicKey   = self.get_argument('publicKey')
        address = WT.pubkey_to_address(publicKey)
        claims = db.claims.find_one({'_id':address})
        trans,msg = WT.claim_gas(address,h,claims,db)
        if trans:
            print 'True'
            self.write(json.dumps({'result':True, 'transaction':trans}))
        else:
            print 'False'
            self.write(json.dumps({'result':True, 'error':msg}))

class BroadcastHandler(CORSHandler):
    def post(self):
        print '%s %s' % (datetime.now(),self.request.path),
        net = self.request.path.split('/')[1]
        transaction = self.get_argument('transaction')
        signature   = self.get_argument('signature')
        publicKey   = self.get_argument('publicKey')
        if not WT.verify(publicKey, transaction, signature):
            msg = 'invalid signature'
            print 'False',msg
            self.write(json.dumps({'result':False,'error':msg}))
        regtx = transaction + '014140' + signature + '2321' + WT.pubkey_to_compress(publicKey) + 'ac'
        result, msg = WT.send_transaction_to_node(regtx, transaction, net)
        if result:
            print 'True'
            self.write(json.dumps({'result':True,'txid':msg}))
        else:
            print 'False',msg
            self.write(json.dumps({'result':False,'error':msg}))


application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/testnet/address/(\w{33,34})', BrowserHandler),
        (r'/mainnet/address/(\w{33,34})', BrowserHandler),
        (r'/testnet/claim/(\w{33,34})', BrowserHandler),
        (r'/mainnet/claim/(\w{33,34})', BrowserHandler),
        (r'/testnet/transaction/(\w{64})', BrowserHandler),
        (r'/mainnet/transaction/(\w{64})', BrowserHandler),
        (r'/testnet/block/(\d{1,10})', BrowserHandler),
        (r'/mainnet/block/(\d{1,10})', BrowserHandler),
        (r'/testnet/height', HeightHandler),
        (r'/mainnet/height', HeightHandler),
        (r'/testnet/transfer', TransferHandler),
        (r'/mainnet/transfer', TransferHandler),
        (r'/testnet/gas', GasHandler),
        (r'/mainnet/gas', GasHandler),
        (r'/testnet/broadcast', BroadcastHandler),
        (r'/mainnet/broadcast', BroadcastHandler),
        ])

if __name__ == "__main__":
    application.listen(PORT)
    tornado.ioloop.IOLoop.instance().start()
