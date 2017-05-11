import tornado.ioloop
import tornado.web
from pymongo import MongoClient
import json
from datetime import datetime

MC = MongoClient('mongodb://127.0.0.1:27017', maxPoolSize=50)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("""<h1>Simple AntShares BlockChain Browser!</h1>
                    <ul>
                        <li>/{net}/height</li>
                        <li>/{net}/block/{block}</li>
                        <li>/{net}/transaction/{txid}</li>
                        <li>/{net}/address/{address}</li>
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
        ])

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
