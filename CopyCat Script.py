import websocket
import threading
import json
import requests

# Replace these with the API keys of your main account and other accounts
main_account_api_key = "api"
main_account_secret_key = "key"

other_accounts = [
    {
        "api_key": "api",
        "secret_key": "key"
    },
    # ... add more accounts as needed
]

# Bybit WebSocket API base URL for testnet
ws_base_url = "wss://stream-testnet.bybit.com/realtime"

# Bybit REST API base URL for testnet
rest_base_url = "https://api-testnet.bybit.com"

def set_leverage(other_account, symbol, leverage, mode):
    params = {
        "api_key": other_account["api_key"],
        "symbol": symbol,
        "leverage": leverage,
        "mode": mode,
    }
    response = requests.post(rest_base_url + "/v2/private/position/leverage/save", data=params)
    return response.json()

def create_order(other_account, order_params):
    order_params["api_key"] = other_account["api_key"]
    response = requests.post(rest_base_url + "/v2/private/order/create", data=order_params)
    return response.json()

def get_existing_order(other_account, order_link_id):
    params = {
        "api_key": other_account["api_key"],
        "order_link_id": order_link_id,
    }
    response = requests.get(rest_base_url + "/v2/private/order", params=params)
    return response.json()

def update_order(other_account, order_id, order_params):
    order_params["api_key"] = other_account["api_key"]
    order_params["order_id"] = order_id
    response = requests.post(rest_base_url + "/v2/private/order/replace", data=order_params)
    return response.json()

def copy_order(main_account_order, other_account):
    # Check if the order is in a relevant state
    if main_account_order["order_status"] not in ["New", "PartiallyFilled"]:
        return

    # Set leverage and margin mode
    symbol = main_account_order["symbol"]
    leverage = main_account_order["leverage"]
    mode = "isolated"  # Force isolated margin mode
    set_leverage(other_account, symbol, leverage, mode)

    # Prepare order parameters
    order_params = {
        "side": main_account_order["side"],
        "symbol": symbol,
        "order_type": main_account_order["order_type"],
        "qty": main_account_order["qty"],
        "price": main_account_order["price"],
        "time_in_force": main_account_order["time_in_force"],
        "reduce_only": main_account_order["reduce_only"],
        "close_on_trigger": main_account_order["close_on_trigger"],
        "order_link_id": main_account_order["order_link_id"],
    }

    # Add stop loss and take profit parameters if available
    if main_account_order["stop_loss"]:
        order_params["stop_loss"] = main_account_order["stop_loss"]
    if main_account_order["take_profit"]:
        order_params["take_profit"] = main_account_order["take_profit"]

    # Check if the order already exists in the other account
    existing_order = get_existing_order(other_account, main_account_order["order_link_id"])

    if existing_order and existing_order["result"]:
        # Update the existing order
                order_id = existing_order["result"]["order_id"]
                update_order(other_account, order_id, order_params)
    else:
        # Create a new order
        create_order(other_account, order_params)

def on_message(ws, message):
    data = json.loads(message)

    if "topic" in data and data["topic"].startswith("order"):
        order_data = data["data"]
        for other_account in other_accounts:
            copy_order(order_data, other_account)

def on_error(ws, error):
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connected")
    ws.send(json.dumps({
        "op": "auth",
        "args": [main_account_api_key, main_account_secret_key]
    }))
    ws.send(json.dumps({
        "op": "subscribe",
        "args": ["order"]
    }))

def start_websocket_listener():
    ws_url = f"{ws_base_url}?api_key={main_account_api_key}"
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    ws.run_forever()

if __name__ == "__main__":
    ws_thread = threading.Thread(target=start_websocket_listener)
    ws_thread.start()
