from flask import Flask, request, render_template, jsonify, session, redirect, url_for
from flask_cors import CORS
from shoonyapy import ShoonyaApi
import pyotp
import logging
import pandas as pd
import numpy as np
from urllib3.exceptions import NameResolutionError
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure key
CORS(app)  # Enable CORS for webhook handling

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Patch ShoonyaApi to fix TypeError and add input validation
def patched_post_helper(self, route, params=None):
    try:
        if not self._root_url:
            raise ValueError("API root URL is not set")
        response = self._session.post(
            f"{self._root_url}/{route}",
            data=params or self._default_payload,
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()
    except NameResolutionError as e:
        logging.error(f"DNS resolution failed: {e}")
        raise Exception("Failed to resolve API endpoint. Check network or endpoint URL.")
    except Exception as e:
        logging.error(f"Error in _post_helper: {e}")
        raise Exception(f"API request failed: {str(e)}")

ShoonyaApi._post_helper = patched_post_helper

# Global API instance
shoonya_api = None

def validate_credentials(credentials):
    """Validate input credentials."""
    required_fields = ['userid', 'pan_or_dob', 'vendor_code', 'api_secret', 'imei', 'totp_secret']
    for field in required_fields:
        if not credentials.get(field) or not str(credentials[field]).strip():
            raise ValueError(f"Missing or invalid {field}")
    return True

@app.route('/')
def index():
    if 'jKey' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    global shoonya_api
    try:
        data = request.form
        credentials = {
            'userid': data.get('user_id'),
            'pan_or_dob': data.get('pan_or_dob'),
            'vendor_code': data.get('vendor_code'),
            'api_secret': data.get('api_secret'),
            'imei': data.get('imei'),
            'totp_secret': data.get('totp_secret')
        }

        # Validate inputs
        validate_credentials(credentials)

        # Generate TOTP
        totp = pyotp.TOTP(credentials['totp_secret'])
        twoFA = totp.now()

        # Initialize Shoonya API with correct endpoint
        shoonya_api = ShoonyaApi(
            userid=credentials['userid'],
            pan_or_dob=credentials['pan_or_dob'],
            vendor_code=credentials['vendor_code'],
            api_secret=credentials['api_secret'],
            imei=credentials['imei'],
            base_url='https://api.shoonya.com'  # Correct endpoint
        )

        # Login
        result = shoonya_api.login(twoFA=twoFA)
        if result.get('stat') == 'Ok':
            session['jKey'] = result['susertoken']
            logging.info(f"Login successful for user: {credentials['userid']}")
            return jsonify({'status': 'success', 'message': 'Login successful'})
        else:
            logging.error(f"Login failed: {result}")
            return jsonify({'status': 'error', 'message': 'Login failed. Check credentials.'}), 400
    except ValueError as e:
        logging.error(f"Validation error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logging.error(f"Login error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/dashboard')
def dashboard():
    if 'jKey' not in session or not shoonya_api:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    global shoonya_api
    session.pop('jKey', None)
    shoonya_api = None
    logging.info("User logged out")
    return redirect(url_for('index'))

@app.route('/get_balance')
def get_balance():
    if not shoonya_api:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    try:
        balance = shoonya_api.get_limits()
        return jsonify({'status': 'success', 'balance': balance.get('cash', 0)})
    except Exception as e:
        logging.error(f"Balance fetch error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_positions')
def get_positions():
    if not shoonya_api:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    try:
        positions = shoonya_api.get_positions()
        df = pd.DataFrame(positions)
        return jsonify({'status': 'success', 'positions': df.to_dict(orient='records')})
    except Exception as e:
        logging.error(f"Positions fetch error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_orders')
def get_orders():
    if not shoonya_api:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    try:
        orders = shoonya_api.get_orders()
        return jsonify({'status': 'success', 'orders': orders})
    except Exception as e:
        logging.error(f"Orders fetch error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/square_off', methods=['POST'])
def square_off():
    if not shoonya_api:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    try:
        data = request.json
        symbol = data['symbol']
        quantity = int(data['quantity'])
        position = next((p for p in shoonya_api.get_positions() if p['tsym'] == symbol), None)
        if not position:
            return jsonify({'status': 'error', 'message': 'Position not found'}), 400
        buy_sell = 'S' if int(position['netqty']) > 0 else 'B'
        result = shoonya_api.place_order(
            buy_sell=buy_sell,
            tradingsymbol=symbol,
            exchange='NFO',
            quantity=quantity,
            price=0,
            product='M',
            order_type='MKT'
        )
        logging.info(f"Squared off position: {symbol}, Order ID: {result.get('norenordno')}")
        return jsonify({'status': 'success', 'message': 'Squared off', 'order_id': result.get('norenordno')})
    except Exception as e:
        logging.error(f"Square off error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        config = request.json
        session['trade_config'] = config
        logging.info(f"Trade config saved: {config}")
        return jsonify({'status': 'success', 'message': 'Configuration saved'})
    except Exception as e:
        logging.error(f"Config save error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    if not shoonya_api:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    try:
        signal = request.json
        config = session.get('trade_config', {})
        if not config:
            return jsonify({'status': 'error', 'message': 'No trade configuration'}), 400

        instrument_type = config.get('instrument_type')
        index = config.get('index')
        trade_type = config.get('trade_type')
        expiry = config.get('expiry')
        strike = config.get('strike')

        symbol = index
        if instrument_type == 'option':
            strike_map = {'atm': 'ATM', 'otm1': 'OTM1', 'otm2': 'OTM2', 'itm1': 'ITM1', 'itm2': 'ITM2'}
            symbol += f" {expiry.upper()} {strike_map.get(strike, 'ATM')}"
        buy_sell = 'B' if trade_type == 'buy' else 'S'
        quantity = 50  # Example quantity
        result = shoonya_api.place_order(
            buy_sell=buy_sell,
            tradingsymbol=symbol,
            exchange='NFO',
            quantity=quantity,
            price=0,
            product='M',
            order_type='MKT'
        )
        logging.info(f"Webhook order placed: {symbol}, Order ID: {result.get('norenordno')}")
        return jsonify({'status': 'success', 'order_id': result.get('norenordno')})
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)