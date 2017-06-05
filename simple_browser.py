import tornado.ioloop
import tornado.web
from pymongo import MongoClient
import json
from datetime import datetime
from decimal import Decimal as D
from WalletTool import WalletTool as WT
from config import PORT

MC = MongoClient('mongodb://127.0.0.1:27017', maxPoolSize=50)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("""<h1>Simple AntShares BlockChain Browser!</h1>
                    <ul>
                        <li><strong>GET</strong> /{net}/height</li>
                        <li><strong>GET</strong> /{net}/block/{block}</li>
                        <li><strong>GET</strong> /{net}/transaction/{txid}</li>
                        <li><strong>GET</strong> /{net}/address/{address}</li>
                        <li><strong>POST</strong> /{net}/transfer</li>
                        <li><strong>POST</strong> /{net}/broadcast</li>
                    </ul>
                    """)

class BrowserHandler(tornado.web.RequestHandler):
    def get(self,xid):
        print '%s %s' % (datetime.now(),self.request.path),
        db,table = self.request.path.split('/')[1:3]
        if 'block' == table:
            xid = int(xid)
        table = MC[db][table+'s'] if table!='address' else MC[db][table+'es']
        result = table.find_one({'_id':xid})
        if result:
            print 'True'
            self.write(json.dumps(result))
        else:
            print 'False'
            self.write(json.dumps({}))

class HeightHandler(tornado.web.RequestHandler):
    def get(self):
        db = MC[self.request.path.split('/')[1]]
        h = db.blocks.count()
        print '%s %s' % (datetime.now(),self.request.path),'True'
        self.write(json.dumps({'height':h}))

class TransferHandler(tornado.web.RequestHandler):
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

class BroadcastHandler(tornado.web.RequestHandler):
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
        (r'/testnet/address/(\w{34})', BrowserHandler),
        (r'/mainnet/address/(\w{34})', BrowserHandler),
        (r'/testnet/transaction/(\w{64})', BrowserHandler),
        (r'/mainnet/transaction/(\w{64})', BrowserHandler),
        (r'/testnet/block/(\d{1,10})', BrowserHandler),
        (r'/mainnet/block/(\d{1,10})', BrowserHandler),
        (r'/testnet/height', HeightHandler),
        (r'/mainnet/height', HeightHandler),
        (r'/testnet/transfer', TransferHandler),
        (r'/mainnet/transfer', TransferHandler),
        (r'/testnet/broadcast', BroadcastHandler),
        (r'/mainnet/broadcast', BroadcastHandler),
        ])

if __name__ == "__main__":
    application.listen(PORT)
    tornado.ioloop.IOLoop.instance().start()
