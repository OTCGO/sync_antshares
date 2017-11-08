# sync_antshares
同步小蚁区块数据并实时计算UTXO

### 安装
1. 安装MongoDB(v3.4.2,其它版本未经测试，本程序未对MongoDB做任何配置)
2. 安装其它Python依赖库：
```
pip install -r requirements.txt
```



### 示例
获取帮助

```
python sync_antshares.py -h
```

从 本地节点 同步 测试网 数据至 本地MongoDB

```
python sync_antshares.py
```
从 本地节点 同步 主网 数据至 本地MongoDB

```
python sync_antshares.py -d mainnet -n http://127.0.0.1:10332
```

从 远程节点 同步 测试网 数据至 远程MongoDB

```
python sync_antshares.py -d testnet -n http://seed5.antshares.org:20332 -m 8.8.8.8:27017
```
