#coding:utf8
from AntShares.Helper import big_or_little

class Order:
    def __init__(self,AssetId,ValueAssertId,Agent,Amount,Price,Client,Inputs):
    self.AssetId = AssetId              #资产编号
    self.ValueAssetId = ValueAssertId    #货币编号
    self.Agent = Agent                  #代理人的合约散列,即代理人的小蚁地址
    self.Amount = Amount                #买入或卖出的数量，正数表示买入，负数表示卖出
    self.Price = Price                  #价格
    self.Client = Client                #委托人的合约散列
    self.Inputs = Inputs                #输入列表
    self.__scripts  = []                #用于验证该订单的脚本列表
    def getScripts(self):
        return self.__scripts
    def setScripts(self, s):
        self.__scripts = s

    def Deserialize(self,reader):
        ((ISignable)this).DeserializeUnsigned(reader);
        Scripts = reader.ReadSerializableArray<Witness>();

    def SerializeInTransaction(self,writer):
        writer.writeFixed8(self.Amount)
        writer.writeFixed8(self.Price)
        writer.writeBytes(big_or_little(self.Client))
        writer.writeSerializableArray(self.inputs)
        writer.Write(self.getScripts())

    def SerializeUnsigned(self,writer):
        writer.writeBytes(big_or_little(self.AssetId))
        writer.writeBytes(big_or_little(self.ValueAssetId))
        writer.writeBytes(big_or_little(self.Agent))
        writer.writeFixed8(self.Amount)
        writer.writeFixed8(self.Price)
        writer.writeBytes(big_or_little(self.Client))
        writer.writeSerializableArray(self.inputs)
