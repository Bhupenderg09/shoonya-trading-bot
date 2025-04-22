from flask import Flask, request, jsonify, render_template
from shoonyapy import NorenApi
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store Shoonya API instance
shoonya_api = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    global shoonya_api
    try:
        data = request.json
        if not all(key in data for key in ['userid', 'password', 'twoFA', 'vendor_code', 'api_secret', 'imei']):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
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
            logger.info(f"Login successful for user {data['userid']}")
            return jsonify({'status': 'success', 'jKey': resp})
        return jsonify({'status': 'error', 'message': 'Login failed'}), 401
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Login error: {str(e)}'}), 500

@app.route('/balance')
def get_balance():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        balance = shoonya_api.get_limits()
        return jsonify(balance)
    except Exception as e:
        logger.error(f"Balance error: {str(e)}")
        return jsonify({'error': f'Failed to fetch balance: {str(e)}'}), 500

@app.route('/positions')
def get_positions():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        positions = shoonya_api.get_positions()
        return jsonify(positions)
    except Exception as e:
        logger.error(f"Positions error: {str(e)}")
        return jsonify({'error': f'Failed to fetch positions: {str(e)}'}), 500

@app.route('/orders')
def get_orders():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        orders = shoonya_api.get_order_book()
        return jsonify(orders)
    except Exception as e:
        logger.error(f"Orders error: {str(e)}")
        return jsonify({'error': f'Failed to fetch orders: {str(e)}'}), 500

@app.route('/square_off', methods=['POST'])
def square_off():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        data = request.json
        if not all(key in data for key in ['symbol', 'quantity']):
            return jsonify({'status': 'error', 'message': 'Missing symbol or quantity'}), 400
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
        logger.info(f"Square-off order placed: {data['symbol']}, quantity: {data['quantity']}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Square-off error: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Square-off failed: {str(e)}'}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    if not shoonya_api:
        return jsonify({'error': 'Not logged in'}), 401
    try:
        signal = request.json
        if not signal or 'signal' not in signal or 'symbol' not in signal:
            return jsonify({'status': 'error', 'message': 'Invalid webhook payload'}), 400
        
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        instrument_type = config.get('instrument_type')
        index = config.get('index')
        trade_type = config.get('trade_type')
        expiry = config.get('expiry')
        strike = config.get('strike')

        if not all([instrument_type, index, trade_type, expiry]):
            return jsonify({'status': 'error', 'message': 'Incomplete configuration'}), 400

        symbol = index
        if instrument_type == 'option':
            # Placeholder: Replace with market data for accurate symbol
            symbol += f" {expiry.upper()} {strike.upper()}"

        buy_sell = 'B' if trade_type == 'buy' else 'S'
        quantity = 50  # Consider making configurable
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
        logger.info(f"Webhook order placed: {symbol}, buy/sell: {buy_sell}, quantity: {quantity}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Webhook failed: {str(e)}'}), 500

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        config = request.json
        with open('config.json', 'w') as f:
            json.dump(config, f)
        logger.info("Configuration saved")
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Config save error: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to save config: {str(e)}'}), 500