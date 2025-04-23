from shoonyapy import ShoonyaApi
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'my_secure_shoonya_key_123'
logging.basicConfig(level=logging.DEBUG)  # Debug logging for detailed output

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {str(e)}")
        return {}

def save_config(config):
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving config: {str(e)}")
        return False

def get_expiry_date():
    today = datetime.today()
    days_to_thursday = (3 - today.weekday()) % 7
    expiry = today + timedelta(days=days_to_thursday)
    return expiry.strftime('%Y-%m-%d')

def get_atm_strike(shoonya_api, index='NIFTY'):
    try:
        quotes = shoonya_api.get_quotes(exchange='NSE', token='26000')
        if quotes and quotes.get('stat') == 'Ok':
            spot_price = float(quotes.get('lp', 0))
            atm_strike = round(spot_price / 100) * 100
            return atm_strike
        return None
    except Exception as e:
        logging.error(f"Error fetching ATM strike: {str(e)}")
        return None

def get_option_symbol(shoonya_api, index, strike, option_type, expiry):
    try:
        expiry_str = datetime.strptime(expiry, '%Y-%m-%d').strftime('%y%b').upper()
        symbol = f"{index}{expiry_str}{int(strike)}{option_type.upper()}"
        search_result = shoonya_api.search_scrip(exchange='NFO', searchtxt=symbol)
        if search_result and search_result.get('values'):
            return search_result['values'][0]['tsym']
        return None
    except Exception as e:
        logging.error(f"Error fetching option symbol: {str(e)}")
        return None

@app.route('/')
def index():
    if 'user_id' in session:
        try:
            shoonya_api = session.get('shoonya_api')
            balance = shoonya_api.get_limits().get('cash', 0) if shoonya_api else 0
            orders = shoonya_api.get_order_book() if shoonya_api else []
            orders = [o for o in orders if o.get('status') == 'OPEN'] if orders else []
            return render_template('index.html', user_id=session['user_id'], config=load_config(), balance=balance, orders=orders)
        except Exception as e:
            logging.error(f"Error fetching dashboard data: {str(e)}")
            return render_template('index.html', user_id=session['user_id'], config=load_config(), error=str(e))
    return render_template('index.html', error=None)

@app.route('/login', methods=['POST'])
def login():
    try:
        userid = request.form['user-id']
        password = request.form['password']
        twoFA = request.form['totp']
        vendor_code = request.form['vendor-code']
        api_secret = request.form['api-secret']
        imei = request.form['imei']
        pan_or_dob = request.form['pan-or-dob']

        logging.info(f"Login attempt for user: {userid}")
        logging.debug(f"Input parameters: userid={userid}, pan_or_dob={pan_or_dob}, vendor_code={vendor_code}, api_secret={api_secret}, imei={imei}")

        # Validate pan_or_dob format (basic check)
        if not (len(pan_or_dob) == 10 and pan_or_dob[:5].isalpha() and pan_or_dob[5:9].isdigit() and pan_or_dob[9].isalpha()) and \
           not (len(pan_or_dob) == 8 and pan_or_dob.isdigit()):
            logging.error("Invalid PAN or DOB format")
            return render_template('index.html', error="Invalid PAN (e.g., ABCDE1234F) or DOB (e.g., 01011990)")

        # Initialize ShoonyaApi
        try:
            shoonya_api = ShoonyaApi(
                username=userid,
                password=password,
                pan_or_dob=pan_or_dob
            )
            logging.debug("ShoonyaApi initialized successfully")
        except Exception as e:
            logging.error(f"ShoonyaApi initialization failed: {str(e)}", exc_info=True)
            return render_template('index.html', error=f"Initialization error: {str(e)}")

        # Attempt login
        try:
            login_response = shoonya_api.login(
                twoFA=twoFA,
                vendor_code=vendor_code,
                api_secret=api_secret,
                imei=imei
            )
            logging.debug(f"Login response: {login_response}")
        except Exception as e:
            logging.error(f"Login method failed: {str(e)}", exc_info=True)
            return render_template('index.html', error=f"Login method error: {str(e)}")

        if login_response and login_response.get('stat') == 'Ok':
            session['user_id'] = userid
            session['susertoken'] = login_response.get('susertoken')
            session['shoonya_api'] = shoonya_api
            logging.info("Login successful")
            return redirect(url_for('index'))
        else:
            logging.error(f"Login failed: {login_response}")
            return render_template('index.html', error="Invalid credentials")
    except Exception as e:
        logging.error(f"General login error: {str(e)}", exc_info=True)
        return render_template('index.html', error=f"Login error: {str(e)}")

@app.route('/configure', methods=['POST'])
def configure():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    try:
        config = {
            'instrument_type': request.form['instrument-type'],
            'index': request.form['index'],
            'trade_type': request.form['trade-type'],
            'expiry': request.form['expiry'],
            'strike': request.form['strike']
        }
        if save_config(config):
            logging.info("Configuration saved")
            return redirect(url_for('index'))
        else:
            return render_template('index.html', user_id=session['user_id'], config=load_config(), config_error="Failed to save config")
    except Exception as e:
        logging.error(f"Config error: {str(e)}")
        return render_template('index.html', user_id=session['user_id'], config=load_config(), config_error=str(e))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/webhook', methods=['POST'])
def webhook():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    try:
        data = request.get_json()
        signal = data.get('signal')
        symbol = data.get('symbol')
        logging.info(f"Webhook received: signal={signal}, symbol={symbol}")

        config = load_config()
        if not config or config.get('index') != symbol:
            return jsonify({"error": "Invalid config or symbol"}), 400

        shoonya_api = session.get('shoonya_api')
        if not shoonya_api:
            return jsonify({"error": "API not initialized"}), 500

        if signal.upper() == "BUY" and symbol == "NIFTY":
            expiry = get_expiry_date()
            atm_strike = get_atm_strike(shoonya_api)
            if not atm_strike:
                return jsonify({"error": "Failed to get ATM strike"}), 500

            option_symbol = get_option_symbol(shoonya_api, 'NIFTY', atm_strike, 'CE', expiry)
            if not option_symbol:
                return jsonify({"error": "Failed to get option symbol"}), 500

            order_response = shoonya_api.place_order(
                buy_or_sell='B',
                product_type='I',
                exchange='NFO',
                tradingsymbol=option_symbol,
                quantity=50,
                discloseqty=0,
                price_type='MKT',
                price=0,
                trigger_price=0
            )

            if order_response and order_response.get('stat') == 'Ok':
                logging.info(f"Order placed: {order_response}")
                return jsonify({"status": "success", "message": f"Order placed: {option_symbol}"})
            else:
                logging.error(f"Order failed: {order_response}")
                return jsonify({"error": "Order failed"}), 400
        else:
            logging.error("Invalid signal or symbol")
            return jsonify({"error": "Invalid signal or symbol"}), 400
    except Exception as e:
        logging.error(f"Webhook error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)