from flask import Flask, request, jsonify, render_template
from NorenApi import NorenApi
import json
from shoonyapy import ShoonyaApi

app = Flask(__name__)

# Store Shoonya API instance
shoonya_api = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    global shoonya_api
    data = request.json
    shoonya_api = NorenApi(
        host='https://api.shoonya.com/NorenWClientTP/',
        websocket='wss://api.shoonya.com/NorenWSTP/',
        eodhost='https://api.shoonya.com/chartApi/getdata/'
    )
    resp = shoonya_api.login(
        userid=data['userid'],
        password=data['password'],
        twoFA=data['twoFA'],
        vendor_code=data['vendor_code'],
        api_secret=data['api_secret'],
        imei=data['imei']
    )
    if resp:
        return jsonify({'status': 'success', 'jKey': resp})
    return jsonify({'status': 'error', 'message': 'Login failed'})

@app.route('/balance')
def get_balance():
    if shoonya_api:
        balance = shoonya_api.get_limits()
        return jsonify(balance)
    return jsonify({'error': 'Not logged in'})

@app.route('/positions')
def get_positions():
    if shoonya_api:
        positions = shoonya_api.get_positions()
        return jsonify(positions)
    return jsonify({'error': 'Not logged in'})

@app.route('/orders')
def get_orders():
    if shoonya_api:
        orders = shoonya_api.get_order_book()
        return jsonify(orders)
    return jsonify({'error': 'Not logged in'})

@app.route('/square_off', methods=['POST'])
def square_off():
    data = request.json
    if shoonya_api:
        # Implement square-off logic (simplified)
        result = shoonya_api.place_order(
            buy_or_sell='S' if data['quantity'] > 0 else 'B',
            product_type='I',
            exchange='NFO',
            tradingsymbol=data['symbol'],
            quantity=abs(data['quantity']),
            discloseqty=0,
            price_type='MKT',
            price=0
        )
        return jsonify(result)
    return jsonify({'error': 'Not logged in'})

@app.route('/webhook', methods=['POST'])
def webhook():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'})
    signal = request.json
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    instrument_type = config['instrument_type']
    index = config['index']
    trade_type = config['trade_type']
    expiry = config['expiry']
    strike = config['strike']

    symbol = index
    if instrument_type == 'option':
        # Simplified strike logic (extend with market data)
        symbol += f" {expiry.upper()} {strike.upper()}"

    buy_sell = 'B' if trade_type == 'buy' else 'S'
    quantity = 50  # Example
    result = shoonya_api.place_order(
        buy_or_sell=buy_sell,
        product_type='I',
        exchange='NFO',
        tradingsymbol=symbol,
        quantity=quantity,
        discloseqty=0,
        price_type='MKT',
        price=0
    )
    return jsonify(result)

@app.route('/save_config', methods=['POST'])
def save_config():
    config = request.json
    with open('config.json', 'w') as f:
        json.dump(config, f)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(debug=True)