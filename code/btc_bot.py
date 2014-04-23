import hmac, base64, hashlib, urllib, urllib2, time, gzip, json, io, sched, csv, datetime, StringIO, ftplib, cProfile, gc
from time import gmtime, strftime
from time import sleep
from urllib import urlencode
from hashlib import sha512

##############  CONSTANTS  ##############
BTC = 0 # initial bitcoins in simulation
USD = 1000 # initial USD in simulation
FEE = .45 # Exchange's fee
base = 'https://data.mtgox.com/api/2/'
key = '' #PRIVATE, DO NOT DISTRIBUTE
sec = '' #EVEN MORE PRIVATE
ftppassword = ''
ftpusername = ''

##############  CONSTANTS  ##############

##############  HELPER FUNCTIONS  ##############
def sign(path, data):
    mac = hmac.new(base64.b64decode(sec), path+chr(0)+data, hashlib.sha512)
    return base64.b64encode(str(mac.digest()))

def req(path, inp={}, get=False):
    try:
        headers = {
            'User-Agent': "Eppie's EMA Trade Bot",
            'Accept-Encoding': 'GZIP',
        }
        if get:
            get_data = urllib.urlencode(inp)
            url = base + path + "?" + get_data
            request = urllib2.Request(url, headers=headers)
            try:
                response = urllib2.urlopen(request)
            except urllib2.URLError as e:
                print CTime() + 'GET failed due to URLError'
                response = None

        else:
            inp[u'tonce'] = str(int(time.time()*1e6))
            post_data = urllib.urlencode(inp)
            headers.update({
                'Rest-Key': key,
                'Rest-Sign': sign(path, post_data),
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            request = urllib2.Request(base + path, post_data, headers)
            try:
                response = urllib2.urlopen(request, post_data)
            except urllib2.URLError as e:
                print CTime() + 'POST failed due to URLError'
                response = None

    except urllib2.HTTPError as e:
        response = e.fp
        print CTime() + 'request failed due to HTTPError'
    if response != None:
        enc = response.info().get('Content-Encoding')
        if isinstance(enc, str) and enc.lower() == 'gzip':
            buff = io.BytesIO(response.read())
            response = gzip.GzipFile(fileobj=buff)
    try:
        output = json.load(response)
        return output
    except ValueError as e:
        print CTime() + str(e) + '(ValueError)'
        return response

##############  HELPER FUNCTIONS  ##############

##############  DATA INPUT  ##############
def readData(f):
    data_array = []
    with open(f, 'rb') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='|')
        for row in reader:
            row['Date'] = datetime.datetime.strptime(row['Date'],"%m/%d/%Y")
            row['weightedPrice'] = float(row['weightedPrice'])
            data_array.append(row)
    return data_array

def readCandles(f):
    data_array = []
    try:
        with open(f, 'rb') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',', quotechar='|')
            gc.disable()
            for row in reader:
                row['Date'] = datetime.datetime.fromtimestamp(float(row['date']))
                row['weightedPrice'] = float(row['close'])
                data_array.append(row)
        gc.enable()
        return data_array
    except IOError as e:
        print CTime() + str(e) + ' (RAISED BY READCANDLES())'
        return None

def readTrades(f, timeframe):
    data_array = []
    with open(f, 'rb') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='|')
        gc.disable()
        for idx, row in enumerate(reader):
            data_array.append(row)
        gc.enable()
    return data_array

##############  DATA INPUT  ##############

##############  TRADING FUNCTIONS  ##############
def sell(num_btc, num_usd, amount, date, data, fee): #sell bitcoins
    if amount > num_btc:
        return "You don't have that many BTC"
    for row in data:
        if date == row['Date']:
            num_usd = num_usd + (amount * row['weightedPrice']) * (1 - fee/100)
            num_btc = num_btc - amount
            return (num_usd, num_btc)


def buy(num_btc, num_usd, amount, date, data, fee): #buy bitcoins
    if amount > num_usd:
        return "You don't have that many USD"
    for row in data:
        if date == row['Date']:
            num_usd = num_usd - amount
            num_btc = num_btc + (amount / row['weightedPrice']) * (1 - fee/100)
            return (num_usd, num_btc)

##############  TRADING FUNCTIONS  ##############

##############  Min/Max Price  ##############
def maxPrice(data):
    best = 0
    bestDate = datetime.datetime.now()
    for row in data:
        if row['weightedPrice'] > best:
            best = row['weightedPrice']
            bestDate = row['Date']
    return (best, bestDate)

def minPrice(data):
    best = 999999
    bestDate = datetime.datetime.now()
    for row in data:
        if row['weightedPrice'] < best:
            best = row['weightedPrice']
            bestDate = row['Date']
    return (best, bestDate)

##############  Min/Max Price  ##############

##############  Strategies  ##############
def magicStrat(num_btc, num_usd, data, mod, ema1, ema2, threshold): #searches all time for min and max price. Buys at the min and sells at the max.
    buydate = minPrice(data)[1]
    selldate = maxPrice(data)[1]
    x = buy(num_btc, num_usd, num_usd, buydate, data, FEE)
    y = sell(x[1], x[0], x[1], selldate, data, FEE)
    return y

def moduloStrat(num_btc, num_usd, data, mod, ema1, ema2, threshold): #buys/sells every mod days
    index = 0
    for row in data:
        index = index + 1
        if index % mod == 0:
            x = buy(num_btc, num_usd, num_usd, row['Date'], data, FEE)
            num_usd = x[0]
            num_btc = x[1]
        if index % mod == (mod/2):
            x = sell(num_btc, num_usd, num_btc, row['Date'], data, FEE)
            num_usd = x[0]
            num_btc = x[1]
    if num_usd == 0:
        x = sell(num_btc, num_usd, num_btc, TODAY, data, FEE)
        num_usd = x[0]
        num_btc = x[1]
    return (num_usd, num_btc)

def EMA(data, days):
    days = float(days)
    alpha = (2 / (days + 1))
    prices = []
    ema = []
    gc.disable()
    for row in data:
        prices.append(row['weightedPrice'])
    #prices.reverse() #not necessary when using candles
    ema.append(prices[0])
    for index in range(1, len(prices)):
        ema.append(alpha * prices[index] + ((1 - alpha) * ema[index - 1]))
    gc.enable()
    return ema

def EMAstrat(num_btc, num_usd, data, mod, ema1, ema2, threshold):
    ema_short = EMA(data, ema1)
    ema_long = EMA(data, ema2)
    num_trades = 0
    for index in range(len(data)):
        if ((1 - (ema_long[index] / ema_short[index])) * 100) > threshold:
            if num_usd != 0:
                num_btc = num_btc + (num_usd / data[index]['weightedPrice']) * (1 - FEE/100)
                num_usd = 0
                #print 'buying bitcoins, bitcoins received:'
                #print num_btc, data[index]['Date']
                num_trades = num_trades + 1
        if ((1 - (ema_short[index] / ema_long[index])) * 100) > threshold:
            if num_btc != 0:
                num_usd = num_usd + (num_btc * data[index]['weightedPrice']) * (1 - FEE/100)
                num_btc = 0
                #print 'selling bitcoins, dollars received:'
                #print num_usd, data[index]['Date']
                num_trades = num_trades + 1
    return (num_usd, num_btc)

def EMAstrat_backtesting(num_btc, num_usd, data, mod, ema1, ema2, threshold):
    ema_short = ema1
    ema_long = ema2
    num_trades = 0
    for index in range(len(data)):
        if ((1 - (ema_long[index] / ema_short[index])) * 100) > threshold:
            if num_usd != 0:
                num_btc = num_btc + (num_usd / data[index]['weightedPrice']) * (1 - FEE/100)
                num_usd = 0
                #print 'buying bitcoins, bitcoins received:'
                #print num_btc, data[index]['Date']
                num_trades = num_trades + 1
        if ((1 - (ema_short[index] / ema_long[index])) * 100) > threshold:
            if num_btc != 0:
                num_usd = num_usd + (num_btc * data[index]['weightedPrice']) * (1 - FEE/100)
                num_btc = 0
                #print 'selling bitcoins, dollars received:'
                #print num_usd, data[index]['Date']
                num_trades = num_trades + 1
    return (num_usd, num_btc)

def EMAdecision(num_btc, num_usd, data, ema1, ema2, threshold):
    ema_short = EMA(data, ema1)
    ema_long = EMA(data, ema2)
    difference = []
    gc.disable()
    for idx in range(len(ema_short)):
        difference.append(((ema_short[idx]/ema_long[idx])-1)*100)
    gc.enable()
    current_difference = difference[-1]
    print CTime() + '24 hours past EMA difference values:'
    print difference[-24:]
    if current_difference >= threshold:
        return "BTC"
    elif current_difference <= (-1 * threshold):
        return "USD"
    else:
        return "HOLD"

def MACD(data, signal, ema1, ema2, threshold):
    ema_short = EMA(data, ema1)
    ema_long = EMA(data, ema2)
    macd = []
    histogram = []
    gc.disable()
    for i in range(len(ema_short)):
        macd.append(ema_short[i] - ema_long[i])
    days = float(signal)
    alpha = (2 / (days + 1))
    signal = []
    signal.append(macd[0])
    for i in range(1, len(macd)):
        signal.append(alpha * macd[i] + ((1 - alpha) * signal[i - 1]))
    for i in range(len(macd)):
        histogram.append(macd[i] - signal[i])
    gc.enable()
    return histogram

def MACD_backtesting(data, signal, ema1, ema2):
    ema_short = ema1
    ema_long = ema2
    macd = []
    histogram = []
    gc.disable()
    for i in range(len(ema_short)):
        macd.append(ema_short[i] - ema_long[i])
    days = float(signal)
    alpha = (2 / (days + 1))
    signal = []
    signal.append(macd[0])
    for i in range(1, len(macd)):
        signal.append(alpha * macd[i] + ((1 - alpha) * signal[i - 1]))
    for i in range(len(macd)):
        histogram.append(macd[i] - signal[i])
    gc.enable()
    return histogram

def MACDstrat(num_btc, num_usd, data, signal, ema1, ema2, threshold):
    macd = MACD(data, signal, ema1, ema2, threshold)
    num_trades = 0
    for index in range(len(data)):
        if macd[index] > threshold:
            if num_usd != 0:
                num_btc = num_btc + (num_usd / data[index]['weightedPrice']) * (1 - FEE/100)
                num_usd = 0
                #print 'buying bitcoins, bitcoins received:'
                #print num_btc, data[index]['Date']
                num_trades = num_trades + 1
        if macd[index] < threshold:
            if num_btc != 0:
                num_usd = num_usd + (num_btc * data[index]['weightedPrice']) * (1 - FEE/100)
                num_btc = 0
                #print 'selling bitcoins, dollars received:'
                #print num_usd, data[index]['Date']
                num_trades = num_trades + 1
    return (num_usd, num_btc)

def MACDstrat_backtesting(num_btc, num_usd, data, signal, macd, threshold):
    #macd = MACD_backtesting(data, signal, ema1, ema2)
    num_trades = 0
    for index in range(len(data)):
        if macd[index] > threshold:
            if num_usd != 0:
                num_btc = num_btc + (num_usd / data[index]['weightedPrice']) * (1 - FEE/100)
                num_usd = 0
                #print 'buying bitcoins, bitcoins received:'
                #print num_btc, data[index]['Date']
                num_trades = num_trades + 1
        if macd[index] < threshold:
            if num_btc != 0:
                num_usd = num_usd + (num_btc * data[index]['weightedPrice']) * (1 - FEE/100)
                num_btc = 0
                #print 'selling bitcoins, dollars received:'
                #print num_usd, data[index]['Date']
                num_trades = num_trades + 1
    return (num_usd, num_btc)

##############  Strategies  ##############

##############  Strategy Evaluation  ##############
def stratEval(strat, num_btc, num_usd, data, mod=0, ema1=0, ema2=0, threshold=0, macd=0, signal=0):
    if strat.__name__ == 'MACDstrat_backtesting':
        x = strat(num_btc, num_usd, data, signal, macd, threshold)
    else:
        x = strat(num_btc, num_usd, data, mod, ema1, ema2, threshold)
    #num_trades = str(x[2])
    if x[0] == 0:
        usd = x[0]
        btc = x[1]
        x = sell(btc, usd, btc, data[-1]['Date'], data, FEE)
    start_money = num_usd + (num_btc * data[0]['weightedPrice'])
    #print 'Strategy Name: ' + strat.__name__
    #print 'Starting Dollars: $' + str(start_money)
    #print 'Ending Dollars: $' + str(x[0])
    #print 'Raw Profit: ' + "$" + str(x[0] - start_money)
    #print 'Percent Profit: ' + str((x[0] - start_money) / start_money * 100) + "%"
    #print 'Number of Trades: ' + num_trades
    try:
        return ((x[0] - start_money) / start_money) * 100
    except TypeError as e:
        print "TypeError"
        return -200

##############  Strategy Evaluation  ##############

##############  Exchange Interactions  ##############
def getAccountInfo():
    '''Returns a tuple consisting of the
    current fee, the number of bitcoins in the account,
    and the number of USD in the account

    '''
    try:
        output = req('BTCUSD/money/info', {})
        FEE = float(json.dumps(output['data']['Trade_Fee']))
        BTC = json.dumps(output['data']['Wallets']['BTC']['Balance']['value'])
        BTC = BTC.replace('"', "")
        BTC = float(BTC)
        USD = json.dumps(output['data']['Wallets']['USD']['Balance']['value'])
        USD = USD.replace('"', "")
        USD = float(USD)
        return FEE, BTC, USD
    except TypeError as e:
        print CTime() + str(e) + ' (RAISED BY GETACCOUNTINFO())'
        return None, None, None


def goxQuote(quoteType, num_btc):
    '''Quote type should be a string, either "bid" or "ask".
    Amount is the number of BTC you'd like to buy / sell.
    If type is bid, the result is the cost in USD of buying that many BTC.
    If type is ask, the result is the amount of USD you'll receive for selling that many BTC.
    Does not take into account exchange fees.

    '''
    amount = str(num_btc * 100000000)
    output = req('BTCUSD/money/order/quote&type='+ quoteType + '&amount=' + amount, {}, True)
    try:
        result = float(json.dumps(output['data']['amount'])) / 100000
        return result
    except TypeError as e:
        print CTime() + str(e) + ' (RAISED BY GOXQUOTE())'
        return None

def goxBuy(num_btc):
    amount = str(num_btc * 100000000)
    output = req('BTCUSD/money/order/add', {'type':'bid', 'amount_int':amount})
    return output

def goxSell(num_btc):
    amount = str(num_btc * 100000000)
    output = req('BTCUSD/money/order/add', {'type':'ask', 'amount_int':amount})
    return output

##############  Exchange Interactions  ##############

##############  FTP Update  ##############
def HTMLbreak(string):
    '''Used with FTPUpdate(). Returns a string that consists of a break concatenated with the input.

    '''
    return '<br>' + str(string)

def HTMLopen():
    '''Used with FTPUpdate(). Returns a string that consists of the beginning HTML for the file.

    '''
    return '<!DOCTYPE html><head><title>Current BTC information</title></head><body>'

def HTMLclose():
    '''Used with FTPUpdate(). Returns a string that consists of the ending HTML for the file.

    '''
    return '</body></html>'

def FTPupdate(open_price, high_price, low_price):
    '''A function to store the recent price data on an FTP server.
    '''
    session = ftplib.FTP('ftp.abcinnovations.com',ftpusername,ftppassword)
    print session.cwd('btc')
    f = open('index.php','r+')
    f.truncate()
    f.write(HTMLopen() + HTMLbreak('Open Price: ') + str(open_price) + HTMLbreak('High Price: ') + str(high_price) + HTMLbreak('Low Price: ') + str(low_price) + HTMLbreak(' Last updated at: ') + strftime("%m/%d %H:%M:%S") + HTMLclose())
    f.close()
    f = open('index.php','rb')
    try:
        print session.storbinary('STOR index.php', f)
        print session.quit()
        print CTime() + 'updated FTP successfully'
    except EOFError:
        print CTime() + 'couldn\'t update FTP, will try again next time. (EOFError)'
        print session.close()
    f.close()


##############  FTP Update  ##############

##############  Data Output  ##############
def CTime():
    '''A function to pretty print 'Current time: ' for use with console logging
    '''
    return strftime("%m/%d %H:%M:%S") + ': '

def logPrice(open_price, high_price, low_price, close_price):
    '''A function to write the OHLC prices to a csv file
    '''
    date = str(int(time.time()))
    with open("candles2.csv", "a") as myfile:
        myfile.write('\n' + date + ',' + str(open_price) + ',' + str(high_price) + ',' + str(low_price) + ',' + str(close_price))
    myfile.close()

def mainHourlyFunction(enabled=False):
    ''' The function that does the real work. It gets the price data every minute, logs it every hour, and executes the buy/sell orders if EMAdecision() tells it to (and enabled==True)
    '''
    open_price = 0
    high_price = 0
    low_price = 99999
    close_price = 0
    hold_amount = 1300
    print CTime() + str(60-time.time()%60) + ' seconds away'
    while True:
        time.sleep(60-time.time()%60) #sleep until the next minute tick of the clock
        output = req('BTCUSD/money/ticker_fast', {}, True) #get the current price
        #pretty_out = json.dumps(output, sort_keys=True, indent=4, separators=(',', ': '))
        #print pretty_out
        #now = strftime("%Y:%m:%d:%H:%M:%S")
        temp = json.dumps(output['data']['last_all']['value']) #extract price from the received JSON object
        temp = temp.replace('"', "")
        temp = float(temp)
        if json.dumps(output['result']).replace('"', "") == 'success':
            print CTime() + 'successfully retrieved price data'
        if open_price == 0: #update the open/high/low prices
            open_price = temp
            print CTime() + 'updated open price: ' + str(temp)
        if high_price < temp:
            high_price = temp
            print CTime() + 'updated high price: ' + str(temp)
        if low_price > temp:
            low_price = temp
            print CTime() + 'updated low price: ' + str(temp)
        print CTime() + 'Current price: ' + str(temp)
        #FTPupdate(open_price, high_price, low_price) #write to a file and upload to abcinnovations.com/btc
        if (int(3600-time.time()%3600) >= 3555) or (int(3600-time.time()%3600) <= 45): #if we're up to 45 seconds before or after the hour, record the data
            close_price = temp
            logPrice(open_price, high_price, low_price, close_price) #output the hour's data to a file
            print CTime() + 'wrote to log'
            print (open_price, high_price, low_price, close_price)
            open_price = 0 #reset for next hour
            high_price = 0
            low_price = 99999
            data = readCandles('candles2.csv') #load in the full price history
            FEE, BTC, USD = getAccountInfo() #get info from my account
            decision = EMAdecision(BTC, USD, data, 10, 21, .25) #run the EMA calculations to decide which currency to hold presently
            if decision == "BTC" and USD > hold_amount and enabled: #if there are dollars to spend, BUY BTC
                amount_to_buy = (USD - hold_amount) / goxQuote("bid", 1)
                bought = goxBuy(amount_to_buy) #leave hold_amount dollars in the account, but spend the rest on BTC
                print "buying " + str(amount_to_buy) + " BTC"
                print bought
            if decision == "USD" and USD <= hold_amount and enabled: #if we have less than the hold amount, SELL BTC
                sold = goxSell(BTC)
                print "selling " + str(BTC) + " BTC"
                print sold

mainHourlyFunction()
##############  Data Output  ##############

##############  Bitcoin Charts Interaction  ##############
##base = 'http://api.bitcoincharts.com/v1/'
##output = req('trades.csv', {'symbol': 'mtgoxUSD'}, True) #get the current price
##print output


##############  Bitcoin Charts Interaction  ##############

##############  Testing  ##############
def mainEMAbacktest(end_value, candleNumber):
    x = readCandles('candles-' + str(candleNumber) + '.csv')
    results = []
    emas = []
    macds = []
    signal = 16
    myfile = open("EMAbacktesting, old_data, candles-" + str(candleNumber) + ".csv", "a")
    gc.disable()
    for i in range(end_value):
        emas.append(EMA(x, i))
    gc.enable()
    for threshold in range(100):
        for i in range(end_value):
            for j in range(i, end_value):
                result = stratEval(EMAstrat_backtesting, BTC, USD, x, signal=signal, threshold=threshold/100.0, ema1=emas[i], ema2=emas[j])
                myfile.write('\n' + str(result) + ',' + str(i) + ',' + str(j) + ',' + str(threshold/100.0))
    myfile.close()

def mainMACDbacktest():
    end_value = 100
    x = readCandles('candles-0.csv')
    results = []
    emas = []
    macds = []
    signal = 16
    myfile = open("MACDbacktesting, old_data, signal=" + str(signal) + ".csv", "a")
    gc.disable()
    for i in range(end_value):
        emas.append(EMA(x, i))
    for i_ema1 in range(end_value):
        for i_ema2 in range(i_ema1, end_value):
            macds.append(MACD_backtesting(x, signal, emas[i_ema1], emas[i_ema2]))
    gc.enable()
    for threshold in range(100):
        start = 0
        end = 0
        for i in range(len(emas)):
            result = stratEval(MACDstrat_backtesting, BTC, USD, x, signal=signal, threshold=threshold/100.0, macd=macds[i])
            myfile.write('\n' + str(result) + ',' + str(signal) + ',' + str(end) + ',' + str(start) + ',' + str(threshold/100.0))
            if start >= end_value - 1:
                start = end + 1
                end = end + 1
            else:
                start = start + 1
    myfile.close()

#for i in range(54,60):
#    mainEMAbacktest(100, i)
#x = readCandles('candles2.csv')
#y = stratEval(EMAstrat, BTC, USD, x, 0, 10, 21, .25)
#print EMAdecision(BTC, USD, x, 10, 21, 0.25)
##############  Testing  ##############
