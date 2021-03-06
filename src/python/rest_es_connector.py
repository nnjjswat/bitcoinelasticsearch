#!/usr/bin/python
__author__ = "donnydevito"
__copyright__   = "Copyright 2015, donnydevito"
__license__ = "MIT"
# Copyright (c) 2016 currentsea, Joseph Bull 

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import requests, json, re, uuid, datetime, argparse, warnings, pytz
from elasticsearch import Elasticsearch
from time import sleep 

# ***** CHANGE THIS TO BE THE URL OF YOUR ELASTICSEARCH SERVER *****
ELASTICSEARCH_HOST = "http://localhost:9200"

# Bitfinex API time limit in seconds 
API_TIME_LIMIT = 1

# Default index name in elasticsearch to use for the btc_usd market data aggregation
DEFAULT_INDEX_NAME = "btctickerarchive"

# REST API URL for Bitfinex
BITFINEX_REST_API_URL = "https://api.bitfinex.com/v1"

# UTC ALL THE TIME, FOREVER AND EVER. 
TIMEZONE = pytz.timezone('UTC')

# REST API URL for Bitfinex US Dollars to Bitcoin (BTCUSD) Public Ticker
BITFINEX_BTCUSD_TICKER_REST_URL = BITFINEX_REST_API_URL + "/pubticker/BTCUSD"

# REST API URL for Bitfinex US Dollars to Litecoin (LTCUSD) Public Ticker
BITFINEX_LTCUSD_TICKER_REST_URL = BITFINEX_REST_API_URL + "/pubticker/LTCUSD"


BITFINEX_LTCBTC_TICKER_REST_URL = BITFINEX_REST_API_URL + "/pubticker/LTCBTC"

# REST API URL Root For Okcoin
OKCOIN_REST_API_URL = "https://www.okcoin.com/api/v1" 

# REST API URL for OkCoin Public Bitcoin (BTCUSD) Ticker
OKCOIN_BTCUSD_TICKER_REST_URL = OKCOIN_REST_API_URL + "/ticker.do?symbol=btc_usd"

def getArgs(): 
	parser = argparse.ArgumentParser(description='BTC elastic search data collector')
	parser.add_argument('--host', action='store_true', default=False)
	parser.add_argument('--forever', action='store_true', default=False)
	parser.add_argument('--max_records', action='store_true', default=3600)

	# TODO: add more params here

	args = parser.parse_args()
	return args

def getTickerData(tickerUrl): 
	tickerDict = None	
	req = requests.get(tickerUrl)
	if req.status_code < 400: 
		tickerDict = req.json()
	else: 
		print("REQUEST TO A TICKER API FAILED (" + tickerUrl + "): status code " + str(req.status_code))
	return tickerDict

def createMappings(es): 
	mappingCreated = False
	try: 
		bitfinexMapping = {
			"bitfinex": {
				"properties": {
					"uuid": { "type": "string", "index": "no"}, 
					"date": {"type": "date"},
					"last_price": {"type": "float"},
					"timestamp": {"type": "string", "index": "no"},
					"volume": {"type": "float"},
					"high": {"type": "float"},
					"ask": {"type": "float"},
					"low": {"type": "float"},
					"dailyChange": {"type": "float"}, 
					"dailyDelta": {"type" : "float"}, 
					"askVolume": {"type": "float"}, 
					"bidVolume": {"type": "float"},
					"bid": {"type": "float"}
				}
			}
		}
		okcoinMapping = { 
			"okcoin": { 
				"properties": {
					"uuid": { "type": "string", "index": "no"}, 
					"date": {"type":"date"}, 
					"last_price": {"type": "float"}, 
					"timestamp": {"type": "string", "index": "no"},
					"volume": {"type": "float"},
					"high": {"type": "float"},
					"ask": {"type": "float"},
					"low": {"type": "float"},
					"bid": {"type": "float"}
				}
			}
		}
		es.indices.create(DEFAULT_INDEX_NAME)
		es.indices.put_mapping(index=DEFAULT_INDEX_NAME, doc_type="bitfinex", body=bitfinexMapping)
		es.indices.put_mapping(index=DEFAULT_INDEX_NAME, doc_type="okcoin", body=okcoinMapping)
		mappingCreated = True
	except: 
		pass
	return mappingCreated

# Adds ticker item to elasticsearch 
# Uses a random UUID as the ID, can be analyzed via the timestamp in kibana
def addBitfinexItem(es): 
	successful = False
	try: 
		tickerData = getTickerData(BITFINEX_BTCUSD_TICKER_REST_URL) 
		dateQueried = datetime.datetime.fromtimestamp(float(tickerData["timestamp"]), TIMEZONE)
		uniqueIdentifier = uuid.uuid4()
		tickerData["uuid"] = str(uniqueIdentifier)
		tickerData["date"] = dateQueried

		# TODO: compound order book info here 

		putNewDocumentRequest = es.create(index=DEFAULT_INDEX_NAME, doc_type='bitfinex', ignore=[400], id=uniqueIdentifier, body=tickerData)
		successful = putNewDocumentRequest["created"]
	except: 
		pass
	return successful

def addOkCoinItem(es): 
	
	successful = False
	try: 
		tickerData = getTickerData(OKCOIN_BTCUSD_TICKER_REST_URL)
		okCoinTimestamp = tickerData["date"]
		okCoinTickerData = tickerData["ticker"]

		dateQueried = datetime.datetime.fromtimestamp(float(okCoinTimestamp), TIMEZONE)


		uniqueIdentifier = uuid.uuid4()
		okCoinDto = {}


		okCoinDto["uuid"] = str(uniqueIdentifier)
		okCoinDto["date"] = dateQueried
		okCoinDto["timestamp"] = str(okCoinTimestamp)
		okCoinDto["last_price"] = float(okCoinTickerData["last"])
		okCoinDto["volume"] = float(okCoinTickerData["vol"]) 
		okCoinDto["high"] = float(okCoinTickerData["high"])
		okCoinDto["ask"] = float(okCoinTickerData["sell"]) 
		okCoinDto["low"] = float(okCoinTickerData["low"]) 
		okCoinDto["bid"] = float(okCoinTickerData["buy"])


		# TODO: compound order book info here 


		putNewDocumentRequest = es.create(index=DEFAULT_INDEX_NAME, doc_type='okcoin', ignore=[400], id=uniqueIdentifier, body=okCoinDto) 
		successful = putNewDocumentRequest["created"]
	except: 
		pass
	return successful

def updateIndex(es): 
	bitfinexUpdateRequestResult = addBitfinexItem(es)
	okcoinUpdateRequestResult = addOkCoinItem(es)
	logResult(bitfinexUpdateRequestResult)
	logResult(okcoinUpdateRequestResult)
	sleep(API_TIME_LIMIT)
	pass 


def logResult(successful): 
	logTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	if successful == True: 
		print("[" + logTime + "]: 1 document successfully added to the " + DEFAULT_INDEX_NAME + " index.") 
	else: 
		print("[" + logTime + "]: document failed to be successfully added to the " + DEFAULT_INDEX_NAME + " index (API calls too frequent?)")
	pass 

if __name__ == "__main__": 
	args = getArgs()
	warnings.filterwarnings("ignore")
	es = Elasticsearch([ELASTICSEARCH_HOST])
	mappingCreated = createMappings(es)
	logTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	if mappingCreated == True:
		print("[" + logTime + "]: Created ES Mapping " + DEFAULT_INDEX_NAME + " \n Begin data collection...")
	else: 
		print("[" + logTime + "]: Elasticsearch mapping already existed.  \nContinuing data collection...")

	if args.forever == True: 
		while 1 == 1: 
			updateIndex(es)
	else: 
		try: 
			maxRecords = int(args.max_records)
		except TypeError:
			raise IOError("Must enter an integer value for max_records")
		if maxRecords == None or maxRecords <= 0: 
			raise IOError("--max_records must be a positive integer value")
		counter = 0
		while counter != maxRecords: 
			updateIndex(es)
			counter = counter + 1

