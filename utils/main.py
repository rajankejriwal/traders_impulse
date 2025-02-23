import requests
import time
from datetime import datetime, timezone
import mysql.connector
from mysql.connector import Error
from zoneinfo import ZoneInfo
import json
import logging
from ratelimit import limits, sleep_and_retry
import os

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# Configuration
TRADELOCKER_ORDERS_HISTORY_URL = "https://{env}.tradelocker.com/backend-api/trade/accounts/{account_id}/ordersHistory"
TRADELOCKER_REFRESH_URL = "https://{env}.tradelocker.com/backend-api/auth/jwt/refresh"
TRADELOCKER_POSITIONS_URL = (
    "https://{env}.tradelocker.com/backend-api/trade/accounts/{account_id}/positions"
)
TRADELOCKER_POSITION_DELETE_URL = (
    "https://{env}.tradelocker.com/backend-api/trade/positions/{position_id}"
)
TRADELOCKER_STATE_URL = (
    "https://{env}.tradelocker.com/backend-api/trade/accounts/{account_id}/state"
)

DEVELOPER_API_KEY = "tl-lz7odxhh16k61p1qf56kj6rhbo0x3ye1"

# MySQL Database Configuration
db_config = {
    "user": "admin",
    "password": "tQ55Nlgify2JGSnKwCAi",
    "host": "tradersimpulse-main.c78skiy68i07.us-east-1.rds.amazonaws.com",
    "database": "tradersimpulse",
}

# Bubble endpoint for sending notifications
BUBBLE_NOTIFICATION_URL = "https://tradersimpulse.com/api/1.1/wf/notify_condition_met"

# **Hardcoded Bubble API Token**
BUBBLE_API_TOKEN = (
    "e1862aa5b08b6383a9f49f4adf206ea6"  # Replace with your actual Bubble API token
)

# Define the rate limits (per second)
RATE_LIMITS = {
    "GET_ACCOUNTS": {"calls": 2, "period": 1},
    "GET_EXECUTIONS": {"calls": 2, "period": 1},
    "GET_INSTRUMENTS": {"calls": 2, "period": 1},
    "GET_ORDERS": {"calls": 1, "period": 1},
    "GET_ORDERS_HISTORY": {"calls": 1, "period": 1},
    "GET_POSITIONS": {"calls": 1, "period": 1},
    "GET_ACCOUNTS_STATE": {"calls": 4, "period": 2},
    "GET_INSTRUMENT_DETAILS": {"calls": 2, "period": 1},
    "GET_TRADE_SESSIONS": {"calls": 2, "period": 1},
    "GET_SESSION_STATUSES": {"calls": 2, "period": 1},
    "PLACE_ORDER": {"calls": 5, "period": 1},
    "MODIFY_ORDER": {"calls": 5, "period": 1},
    "MODIFY_POSITION": {"calls": 5, "period": 1},
    "DAILY_BAR": {"calls": 5, "period": 1},
    "QUOTES": {"calls": 10, "period": 1},
    "DEPTH": {"calls": 10, "period": 1},
    "TRADES": {"calls": 5, "period": 1},
    "QUOTES_HISTORY": {"calls": 1, "period": 1},
}

# Initialize the notification flag
notification_sent = False


# Function to create rate limiters
def create_rate_limiter(rate_limit_type):
    if rate_limit_type not in RATE_LIMITS:
        # Default rate limit if not specified
        return lambda f: f

    calls = RATE_LIMITS[rate_limit_type]["calls"]
    period = RATE_LIMITS[rate_limit_type]["period"]

    def decorator(func):
        @sleep_and_retry
        @limits(calls=calls, period=period)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Define rate limiters for each API call
def get_rate_limit_decorator(rate_limit_type):
    return create_rate_limiter(rate_limit_type)


# Function to send notification to Bubble when a trading condition is met
def notify_bubble_of_condition(
    account_id, condition_name, message, unique_id, user, position_id=None
):
    payload = {
        "account_id": account_id,
        "condition_name": condition_name,
        "position_id": position_id,
        "message": message,
        "unique_id": unique_id,
        "user": user,
    }

    try:
        response = requests.post(BUBBLE_NOTIFICATION_URL, json=payload)
        if response.status_code == 200:
            logger.info(
                f"Successfully notified Bubble about {condition_name} for account {account_id}."
            )
        else:
            logger.error(
                f"Failed to notify Bubble. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.error(f"Error while notifying Bubble: {e}")


# Function to send the initial notification with unique ID
def send_initial_notification(unique_id):
    notification_url = "https://tradersimpulse.bubbleapps.io/api/1.1/wf/server-status"
    payload = {"enabled": "yes", "unique_id": unique_id}

    try:
        response = requests.post(notification_url, json=payload)
        if response.status_code == 200:
            logger.info("Initial notification sent successfully.")
        else:
            logger.error(
                f"Failed to send initial notification. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.error(f"Error while sending initial notification: {e}")


# Establish a connection to the MySQL database
def create_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            logger.info("Connected to MySQL Database")
            return connection
    except Error as e:
        logger.error(f"Error while connecting to MySQL: {e}")
        return None


# Decorated function to fetch trading account by unique ID
@get_rate_limit_decorator("GET_ACCOUNTS")
def fetch_trading_account_by_unique_id(unique_id):
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM trading_accounts WHERE unique_id = %s"
            cursor.execute(query, (unique_id,))
            account = cursor.fetchone()
            cursor.close()
            connection.close()
            if account:
                logger.info("Successfully fetched account from MySQL")

                # Convert enabled flags to booleans
                bool_fields = [
                    "daily_loss_limit_enabled",
                    "daily_profit_target_enabled",
                    "weekly_profit_target_enabled",
                    "max_overall_profit_enabled",
                    "max_num_of_trades_enabled",
                    "trading_window_enabled",
                    "max_position_size_enabled",
                ]
                for field in bool_fields:
                    try:
                        account[field] = bool(int(account.get(field, 0)))
                    except (ValueError, TypeError):
                        account[field] = False

                # Convert limit values to appropriate types
                float_fields = [
                    "daily_loss_limit",
                    "daily_profit_target",
                    "weekly_profit_target",
                    "max_overall_profit",
                    "max_position_size",
                ]
                for field in float_fields:
                    try:
                        account[field] = float(account.get(field, 0.0))
                    except (ValueError, TypeError):
                        account[field] = 0.0

                # Convert integer fields
                try:
                    account["max_num_of_trades"] = int(
                        account.get("max_num_of_trades", 0)
                    )
                except (ValueError, TypeError):
                    account["max_num_of_trades"] = 0

                # Convert other fields
                account["trading_window_start_time"] = account.get(
                    "trading_window_start_time"
                )
                account["trading_window_end_time"] = account.get(
                    "trading_window_end_time"
                )
                account["user_time_zone"] = account.get("user_time_zone")
                account["user"] = account.get("user")

                # Convert equity values
                try:
                    account["equity_eod"] = (
                        float(account.get("equity_eod"))
                        if account.get("equity_eod") is not None
                        else None
                    )
                except (ValueError, TypeError):
                    account["equity_eod"] = None
                try:
                    account["equity_eow"] = (
                        float(account.get("equity_eow"))
                        if account.get("equity_eow") is not None
                        else None
                    )
                except (ValueError, TypeError):
                    account["equity_eow"] = None
                try:
                    account["initial_balance"] = float(
                        account.get("initial_balance", 1000)
                    )
                except (ValueError, TypeError):
                    account["initial_balance"] = 1000.0

                account["env"] = account.get("env", "demo")

                # Handle datetime fields
                expiry_time = account.get("expiry_time")
                if expiry_time and expiry_time.tzinfo is None:
                    expiry_time = expiry_time.replace(tzinfo=timezone.utc)
                account["expiry_time"] = expiry_time

                trading_window_enabled_since = account.get(
                    "trading_window_enabled_since"
                )
                if (
                    trading_window_enabled_since
                    and trading_window_enabled_since.tzinfo is None
                ):
                    trading_window_enabled_since = trading_window_enabled_since.replace(
                        tzinfo=timezone.utc
                    )
                account["trading_window_enabled_since"] = trading_window_enabled_since

                # Log the enabled flags and other critical values
                logger.info("Enabled flags:")
                for field in bool_fields:
                    logger.info(f"  {field}: {account[field]}")

                logger.info("Limit values:")
                for field in float_fields + ["max_num_of_trades"]:
                    logger.info(f"  {field}: {account[field]}")

                logger.info("Trading window times:")
                logger.info(
                    f"  trading_window_start_time: {account['trading_window_start_time']}"
                )
                logger.info(
                    f"  trading_window_end_time: {account['trading_window_end_time']}"
                )
                logger.info(f"User time zone: {account['user_time_zone']}")

                return account
            else:
                logger.warning(f"Account not found for unique_id {unique_id}")
                return None
        except Error as e:
            logger.error(f"Error fetching account: {e}")
            return None
    return None


# Decorated function to refresh bearer token
@get_rate_limit_decorator(
    "GET_ACCOUNTS_STATE"
)  # Assuming token refresh is under GET_ACCOUNTS_STATE rate limits
def refresh_bearer_token(refresh_token, env):
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "developer-api-key": DEVELOPER_API_KEY,
    }
    payload = {"refreshToken": refresh_token}
    logger.info("Attempting to refresh the token...")

    refresh_url = TRADELOCKER_REFRESH_URL.format(env=env)

    try:
        response = requests.post(refresh_url, headers=headers, json=payload, timeout=10)
        # No need for respect_rate_limit here as decorators handle it

        if response.status_code == 201:
            new_token_data = response.json()
            new_bearer_token = new_token_data.get("accessToken")
            new_refresh_token = new_token_data.get("refreshToken")
            expire_date_str = new_token_data.get("expireDate")

            expiry_time = datetime.strptime(
                expire_date_str, "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)
            logger.info(f"Successfully refreshed tokens. Expiry time: {expiry_time}")
            return new_bearer_token, new_refresh_token, expiry_time
        else:
            logger.error(
                f"Failed to refresh token: {response.status_code} - {response.text}"
            )
            return None, None, None
    except requests.Timeout:
        logger.error("Request timed out while attempting to refresh the token.")
        return None, None, None
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        return None, None, None


# Decorated function to fetch account equity and open positions
@get_rate_limit_decorator("GET_ACCOUNTS_STATE")
def fetch_account_equity_and_open_positions(
    bearer_token, account_id, acc_num, env, retries=3
):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "accNum": str(acc_num),
        "developer-api-key": DEVELOPER_API_KEY,
    }
    url = TRADELOCKER_STATE_URL.format(env=env, account_id=account_id)
    logger.info(
        f"Fetching account equity and today's trades for account_id: {account_id}, accNum: {acc_num}..."
    )

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            # No need for respect_rate_limit here as decorators handle it
            if response.status_code == 200:
                account_data = response.json()
                account_details = account_data.get("d", {}).get(
                    "accountDetailsData", []
                )
                if len(account_details) >= 26:
                    account_equity = float(account_details[1])
                    trades_today = int(account_details[21])  # todayTradesCount
                    open_positions_count = int(account_details[24])  # positionsCount
                    orders_count = int(account_details[25])  # ordersCount
                    logger.info(
                        f"Fetched equity: {account_equity}, Trades today: {trades_today}, Open positions: {open_positions_count}, Orders count: {orders_count}"
                    )
                    return (
                        account_equity,
                        trades_today,
                        open_positions_count,
                        orders_count,
                    )
                else:
                    logger.warning("Account details data is incomplete.")
            else:
                logger.error(
                    f"Error fetching equity: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Error while fetching equity: {e}")
        logger.info(f"Retrying... ({attempt + 1}/{retries})")
        time.sleep(1)  # Brief pause before retry
    logger.error("Failed to fetch account equity after retries.")
    return None, None, None, None


# Decorated function to fetch orders history
@get_rate_limit_decorator("GET_ORDERS_HISTORY")
def fetch_orders_history(bearer_token, account_id, acc_num, env, retries=3):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "accNum": str(acc_num),
        "developer-api-key": DEVELOPER_API_KEY,
    }
    url = TRADELOCKER_ORDERS_HISTORY_URL.format(env=env, account_id=account_id)
    logger.info(f"Fetching orders history for account_id: {account_id}...")

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                orders_history = response.json().get("d", {}).get("ordersHistory", [])
                logger.info(
                    f"Fetched orders history with {len(orders_history)} orders."
                )
                return orders_history
            else:
                logger.error(
                    f"Error fetching orders history: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Error while fetching orders history: {e}")
        logger.info(f"Retrying... ({attempt + 1}/{retries})")
        time.sleep(1)  # Brief pause before retry
    logger.error("Failed to fetch orders history after retries.")
    return []


# Decorated function to fetch open positions
@get_rate_limit_decorator("GET_POSITIONS")
def fetch_open_positions(bearer_token, account_id, acc_num, env, retries=3):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "accNum": str(acc_num),
        "developer-api-key": DEVELOPER_API_KEY,
    }
    url = TRADELOCKER_POSITIONS_URL.format(env=env, account_id=account_id)
    logger.info(f"Fetching open positions for account_id: {account_id}...")

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                positions_data = response.json().get("d", {}).get("positions", [])
                if positions_data:
                    positions_info = []
                    for position in positions_data:
                        position_dict = {
                            "id": position[0],
                            "tradableInstrumentId": position[1],
                            "routeId": position[2],
                            "side": position[3],
                            "qty": position[4],
                            "avgPrice": position[5],
                            "stopLossId": position[6],
                            "takeProfitId": position[7],
                            "openDate": position[8],
                            "unrealizedPl": position[9],
                            "strategyId": position[10],
                        }
                        positions_info.append(position_dict)
                    logger.info(f"Fetched open positions: {positions_info}")
                    return positions_info
                else:
                    logger.info("No open positions found.")
                    return []
            else:
                logger.error(
                    f"Error fetching open positions: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Error while fetching open positions: {e}")
        logger.info(f"Retrying... ({attempt + 1}/{retries})")
        time.sleep(1)  # Brief pause before retry
    logger.error("Failed to fetch open positions after retries.")
    return []


# Decorated function to close positions
@get_rate_limit_decorator("MODIFY_POSITION")
def close_positions(bearer_token, acc_num, env, positions_to_close):
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "accept": "application/json",
        "accNum": str(acc_num),
        "Content-Type": "application/json",
        "developer-api-key": DEVELOPER_API_KEY,
    }
    for position in positions_to_close:
        position_id = position["id"]
        qty = position["qty"]
        url = TRADELOCKER_POSITION_DELETE_URL.format(env=env, position_id=position_id)
        payload = {"qty": qty}
        logger.info(f"Closing position {position_id} with qty {qty}...")
        try:
            response = requests.delete(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Successfully closed position {position_id} for qty {qty}")
            else:
                logger.error(
                    f"Failed to close position {position_id}: {response.status_code} - {response.text}"
                )
        except Exception as e:
            logger.error(f"Error while closing position {position_id}: {e}")


# Update tokens, equity, and expiry time in MySQL
def update_tokens_and_equity_in_mysql(
    unique_id, new_access_token, new_refresh_token, equity, expiry_time
):
    connection = create_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            query = """
                UPDATE trading_accounts
                SET access_token = %s, refresh_token = %s, account_equity = %s, expiry_time = %s
                WHERE unique_id = %s
            """
            cursor.execute(
                query,
                (new_access_token, new_refresh_token, equity, expiry_time, unique_id),
            )
            connection.commit()
            cursor.close()
            connection.close()
            logger.info(
                f"Updated tokens, equity, and expiry time for unique_id {unique_id}"
            )
        except Error as e:
            logger.error(f"Error updating account: {e}")


# Function to count unique position IDs opened today using ordersHistory
def count_initial_trades_today(orders_history):
    # Determine today's date in UTC
    today = datetime.now(timezone.utc).date()
    unique_position_ids = set()

    for order in orders_history:
        try:
            # Position ID is at index 16 (0-based index)
            position_id = order[16]
            if not position_id:
                continue  # Skip if position_id is None or empty

            # Open date is at index 13 (assuming openDate is at index 13)
            open_date_str = order[13]
            if not open_date_str:
                continue  # Skip if openDate is None or empty

            open_datetime = datetime.fromtimestamp(
                int(open_date_str) / 1000, timezone.utc
            )
            open_date = open_datetime.date()

            if open_date == today:
                unique_position_ids.add(position_id)
        except (IndexError, ValueError, TypeError) as e:
            logger.error(f"Error processing order: {order}. Error: {e}")
            continue

    initial_trades_today = len(unique_position_ids)
    logger.info(
        f"Number of initial trades today (unique positions opened today): {initial_trades_today}"
    )
    return initial_trades_today


# Check trading conditions and determine which positions to close
def check_trading_conditions_and_close(
    account_info,
    account_equity,
    trades_today,
    open_positions_count,
    daily_loss_limit,
    daily_loss_limit_enabled,
    daily_profit_target,
    daily_profit_target_enabled,
    weekly_profit_target,
    weekly_profit_target_enabled,
    max_overall_profit,
    max_overall_profit_enabled,
    max_num_of_trades,
    max_num_of_trades_enabled,
    positions_info,
    trading_window_enabled,
    trading_window_start_time,
    trading_window_end_time,
    user_time_zone_str,
    max_position_size,
    max_position_size_enabled,  # New parameters
):
    close_all_positions = False
    positions_to_close = []
    equity_eow = account_info.get("equity_eow")
    equity_eod = account_info.get("equity_eod")
    initial_balance = account_info.get("initial_balance", 1000.0)
    user = account_info.get("user")

    logger.debug(f"daily_loss_limit_enabled: {daily_loss_limit_enabled}")
    logger.debug(f"daily_profit_target_enabled: {daily_profit_target_enabled}")
    logger.debug(f"weekly_profit_target_enabled: {weekly_profit_target_enabled}")
    logger.debug(f"max_overall_profit_enabled: {max_overall_profit_enabled}")
    logger.debug(f"max_num_of_trades_enabled: {max_num_of_trades_enabled}")
    logger.debug(f"trading_window_enabled: {trading_window_enabled}")
    logger.debug(f"max_position_size_enabled: {max_position_size_enabled}")
    logger.debug(f"max_position_size: {max_position_size}")

    # 1. Check Max Number of Trades
    if max_num_of_trades_enabled and max_num_of_trades > 0:
        logger.debug(
            f"Trades Today: {trades_today}, Max Allowed Trades: {max_num_of_trades}"
        )
        if trades_today > max_num_of_trades:
            logger.info(
                f"Max number of trades hit: {max_num_of_trades}, Trades today: {trades_today}"
            )
            if open_positions_count > 0:
                close_all_positions = True
                notify_bubble_of_condition(
                    account_info["account_id"],
                    "max_num_of_trades",
                    "Max number of trades was breached. All positions have been closed.",
                    account_info["unique_id"],
                    user,
                )

    # 2. Check Daily Loss Limit using equity_eod
    if (
        daily_loss_limit_enabled
        and daily_loss_limit is not None
        and equity_eod is not None
    ):
        calculated_loss_limit = equity_eod * (1 - daily_loss_limit / 100)
        logger.info(
            f"Checking daily loss limit: {calculated_loss_limit}, Current equity: {account_equity}"
        )
        if account_equity <= calculated_loss_limit:
            logger.info(
                f"Daily loss limit hit: {calculated_loss_limit}, Current equity: {account_equity}"
            )
            if open_positions_count > 0:
                close_all_positions = True
                notify_bubble_of_condition(
                    account_info["account_id"],
                    "daily_loss_limit",
                    "Daily loss limit was breached. All positions have been closed.",
                    account_info["unique_id"],
                    user,  # Include user in the notification
                )

    # 3. Check Daily Profit Target using equity_eod
    if (
        daily_profit_target_enabled
        and daily_profit_target is not None
        and equity_eod is not None
    ):
        calculated_target = equity_eod * (1 + daily_profit_target / 100)
        logger.info(
            f"Checking daily profit target: {calculated_target}, Current equity: {account_equity}"
        )
        if account_equity >= calculated_target:
            logger.info(
                f"Daily profit target hit: {calculated_target}, Current equity: {account_equity}"
            )
            if open_positions_count > 0:
                close_all_positions = True
                notify_bubble_of_condition(
                    account_info["account_id"],
                    "daily_profit_target",
                    "Daily profit target was breached. All positions have been closed.",
                    account_info["unique_id"],
                    user,  # Include user in the notification
                )

    # 4. Check Weekly Profit Target using equity_eow
    if (
        weekly_profit_target_enabled
        and weekly_profit_target is not None
        and equity_eow is not None
    ):
        calculated_weekly_target = equity_eow * (1 + weekly_profit_target / 100)
        logger.info(
            f"Checking weekly profit target: {calculated_weekly_target}, Current equity: {account_equity}"
        )
        if account_equity >= calculated_weekly_target:
            logger.info(
                f"Weekly profit target hit: {calculated_weekly_target}, Current equity: {account_equity}"
            )
            if open_positions_count > 0:
                close_all_positions = True
                notify_bubble_of_condition(
                    account_info["account_id"],
                    "weekly_profit_target",
                    "Weekly profit target was breached. All positions have been closed.",
                    account_info["unique_id"],
                    user,  # Include user in the notification
                )

    # 5. Check Max Overall Profit
    if max_overall_profit_enabled and max_overall_profit is not None:
        calculated_overall_target = initial_balance * (1 + max_overall_profit / 100)
        logger.info(
            f"Checking max overall profit target: {calculated_overall_target}, Current equity: {account_equity}"
        )
        if account_equity >= calculated_overall_target:
            logger.info(
                f"Max overall profit target hit: {calculated_overall_target}, Current equity: {account_equity}"
            )
            if open_positions_count > 0:
                close_all_positions = True
                notify_bubble_of_condition(
                    account_info["account_id"],
                    "max_overall_profit",
                    "Max overall profit target was breached. All positions have been closed.",
                    account_info["unique_id"],
                    user,  # Include user in the notification
                )

    # 6. Check Max Position Size Condition
    if max_position_size_enabled and max_position_size > 0:
        logger.info("Checking Max Position Size condition.")
        for position in positions_info:
            try:
                position_size = float(position["qty"])
                if position_size > max_position_size:
                    excess_qty = position_size - max_position_size
                    excess_qty = round(
                        excess_qty, 8
                    )  # Round to avoid floating point precision issues
                    logger.info(
                        f"Position {position['id']} exceeds max position size. Position size: {position_size}, Limit: {max_position_size}, Excess Qty: {excess_qty}"
                    )

                    # Prepare the position with excess_qty to close only the excess part
                    position_to_close = position.copy()
                    position_to_close["qty"] = excess_qty
                    positions_to_close.append(position_to_close)

                    # Send notification to Bubble
                    notify_bubble_of_condition(
                        account_info["account_id"],
                        "max_position_size",
                        f"Position size {position_size} exceeds the max allowed {max_position_size}. Excess qty {excess_qty} has been closed.",
                        account_info["unique_id"],
                        user,
                        position_id=position["id"],
                    )
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing position {position['id']}: {e}")
                continue

    # Function to check if a time is within the trading window, including handling midnight crossings
    def is_within_trading_window(current_time, start_time, end_time):
        if start_time <= end_time:
            # Normal window (e.g., 09:00 to 17:00)
            return start_time <= current_time <= end_time
        else:
            # Window crosses midnight (e.g., 22:00 to 02:00)
            return current_time >= start_time or current_time <= end_time

    # 7. Check Trading Window with timezone and DST considerations
    if (
        trading_window_enabled
        and trading_window_start_time
        and trading_window_end_time
        and user_time_zone_str
    ):
        try:
            # Create a ZoneInfo instance
            user_timezone = ZoneInfo(user_time_zone_str)
            logger.info(f"User timezone set to: {user_time_zone_str}")

            # Get the current time in UTC and convert to user's timezone
            now_utc = datetime.now(timezone.utc)
            current_time_user_tz = now_utc.astimezone(user_timezone).time()
            logger.info(f"Current time in {user_time_zone_str}: {current_time_user_tz}")

            # Parse trading window start and end times in 24-hour format
            try:
                start_time = datetime.strptime(
                    trading_window_start_time, "%H:%M"
                ).time()
                end_time = datetime.strptime(trading_window_end_time, "%H:%M").time()
                logger.info(f"Trading window: {start_time} to {end_time}")
            except ValueError as ve:
                logger.error(f"Error parsing trading window times: {ve}")
                return close_all_positions, positions_to_close

            # Handle positions that were opened after the trading window was enabled
            trading_window_enabled_since = account_info.get(
                "trading_window_enabled_since"
            )

            for position in positions_info:
                try:
                    open_timestamp_ms = int(position["openDate"])
                    position_open_datetime = datetime.fromtimestamp(
                        open_timestamp_ms / 1000, timezone.utc
                    )
                    position_open_time_user_tz = position_open_datetime.astimezone(
                        user_timezone
                    ).time()
                    logger.info(
                        f"Position {position['id']} opened at {position_open_time_user_tz} in {user_time_zone_str}"
                    )
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"Invalid openDate format for position {position['id']}: {position['openDate']} - Error: {e}"
                    )
                    continue

                if (
                    trading_window_enabled_since
                    and position_open_datetime < trading_window_enabled_since
                ):
                    logger.info(
                        f"Position {position['id']} was opened before trading window was enabled. Skipping this position."
                    )
                    continue

                # Check if the position was opened outside the trading window
                if not is_within_trading_window(
                    position_open_time_user_tz, start_time, end_time
                ):
                    logger.info(
                        f"Position {position['id']} was opened outside the trading window. Scheduling for closure."
                    )
                    positions_to_close.append(position)
                    # Send notification to Bubble
                    notify_bubble_of_condition(
                        account_info["account_id"],
                        "trading_window",
                        "Position was opened outside the trading window. It has been closed.",
                        account_info["unique_id"],
                        user,
                        position_id=position["id"],
                    )

        except Exception as e:
            logger.error(f"Error processing trading window condition: {e}")

    # Return the flags to determine if positions need to be closed
    return close_all_positions, positions_to_close


# Function to fetch unique_id from Bubble API based on EC2 Instance ID using IMDSv2
def fetch_unique_id_from_bubble_api(bubble_api_token):
    try:
        # Obtain IMDSv2 token
        # token_url = "http://169.254.169.254/latest/api/token"
        # token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        # token_response = requests.put(token_url, headers=token_headers, timeout=5)
        # if token_response.status_code == 200:
        #     token = token_response.text
        #     logger.info("Successfully obtained IMDSv2 token.")
        # else:
        #     logger.error(
        #         f"Failed to obtain IMDSv2 token. Status code: {token_response.status_code}"
        #     )
        #     return None

        # # Fetch the EC2 Instance ID using the token
        # metadata_url = "http://169.254.169.254/latest/meta-data/instance-id"
        # metadata_headers = {"X-aws-ec2-metadata-token": token}
        # response = requests.get(metadata_url, headers=metadata_headers, timeout=5)
        # if response.status_code == 200:
        #     instance_id = response.text
        #     logger.info(f"EC2 Instance ID: {instance_id}")
        # else:
        #     logger.error(
        #         f"Failed to fetch instance ID. Status code: {response.status_code}"
        #     )
        #     return None

        # Construct the Bubble API URL to fetch trading_account based on ec2_instance_id
        bubble_api_url = "https://tradersimpulse.com/api/1.1/obj/trading_accounts"

        # Define constraints as a list of dictionaries
        constraints = [
            {
                "key": "ec2_instance_id",
                "constraint_type": "equals",
                # "value": instance_id,
                # "value": "i-0c7e6350368bde5d4",
                "value": os.getenv("container_id"),
            }
        ]

        # Serialize constraints to JSON string
        constraints_json = json.dumps(constraints)

        headers = {
            "Authorization": f"Bearer {bubble_api_token}",
            "Content-Type": "application/json",
        }

        # Make the API request to Bubble with properly encoded constraints
        response = requests.get(
            bubble_api_url,
            headers=headers,
            params={"constraints": constraints_json},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("response", {}).get("results", [])
            logger.debug(
                f"Bubble API Response: {json.dumps(data)}"
            )  # Detailed response logging
            if len(results) == 1:
                unique_id = results[0].get("_id")  # Changed from 'unique_id' to '_id'
                logger.info(f"Fetched unique_id from Bubble: {unique_id}")
                return unique_id
            elif len(results) == 0:
                logger.warning("No trading_account found with this EC2 Instance ID.")
                return None
            else:
                logger.warning(
                    "Multiple trading_accounts found with this EC2 Instance ID."
                )
                return None
        else:
            logger.error(
                f"Failed to fetch unique_id from Bubble. Status code: {response.status_code}, Response: {response.text}"
            )
            return None

    except requests.exceptions.Timeout:
        logger.error("Request timed out while fetching unique_id from Bubble.")
        return None
    except Exception as e:
        logger.error(f"Error fetching unique_id from Bubble: {e}")
        return None


# Main function to fetch data, refresh token, fetch equity and trades, check conditions, and close positions
def main():
    global notification_sent  # Declare the global flag

    # Use the Bubble API token from environment variables
    bubble_api_token = BUBBLE_API_TOKEN
    if not bubble_api_token:
        logger.error("Bubble API token is not available. Exiting script.")
        return

    # Fetch unique_id once before entering the loop
    unique_id = fetch_unique_id_from_bubble_api(bubble_api_token)
    if not unique_id:
        logger.error("Failed to retrieve unique_id. Exiting script.")
        return

    # Send the initial notification if not already sent
    if not notification_sent:
        send_initial_notification(unique_id)
        notification_sent = True  # Update the flag

    while True:
        # Fetch account details inside the loop to get the latest updates
        account = fetch_trading_account_by_unique_id(unique_id)
        if not account:
            logger.error(
                f"Failed to fetch account details for unique_id {unique_id}. Skipping this iteration."
            )
            time.sleep(5)
            continue

        access_token = account["access_token"]
        refresh_token = account["refresh_token"]
        account_id = account["account_id"]
        acc_num = account["accNum"]
        expiry_time = account.get("expiry_time")
        env = account.get("env", "demo")

        # Refresh token if expired
        if expiry_time is None or datetime.now(timezone.utc) >= expiry_time:
            logger.info(
                "Token has expired or expiry time is not set. Refreshing the token..."
            )
            new_tokens = refresh_bearer_token(refresh_token, env)
            if new_tokens:
                new_access_token, new_refresh_token, new_expiry_time = new_tokens
                access_token = new_access_token
                refresh_token = new_refresh_token
                expiry_time = new_expiry_time
                update_tokens_and_equity_in_mysql(
                    unique_id, access_token, refresh_token, None, expiry_time
                )
            else:
                logger.error("Failed to refresh token. Skipping this iteration.")
                time.sleep(2)
                continue

        # Fetch account equity and open positions
        equity_data = fetch_account_equity_and_open_positions(
            access_token, account_id, acc_num, env
        )
        if equity_data is not None:
            account_equity, trades_today, open_positions_count, orders_count = (
                equity_data
            )
            update_tokens_and_equity_in_mysql(
                unique_id, access_token, refresh_token, account_equity, expiry_time
            )

            # Fetch orders history
            orders_history = fetch_orders_history(
                access_token, account_id, acc_num, env
            )
            if orders_history is None:
                logger.error("Failed to fetch orders history. Skipping this iteration.")
                time.sleep(5)
                continue

            # Count unique position IDs opened today
            initial_trades_today = count_initial_trades_today(orders_history)
            adjusted_trades_today = initial_trades_today

            logger.info(f"Trades today (initial): {adjusted_trades_today}")

            # Fetch open positions
            positions_info = fetch_open_positions(
                access_token, account_id, acc_num, env
            )

            # Check trading conditions
            close_all_positions, positions_to_close = (
                check_trading_conditions_and_close(
                    account,
                    account_equity,
                    adjusted_trades_today,
                    open_positions_count,
                    account.get("daily_loss_limit"),
                    account.get("daily_loss_limit_enabled"),
                    account.get("daily_profit_target"),
                    account.get("daily_profit_target_enabled"),
                    account.get("weekly_profit_target"),
                    account.get("weekly_profit_target_enabled"),
                    account.get("max_overall_profit"),
                    account.get("max_overall_profit_enabled"),
                    account.get("max_num_of_trades"),
                    account.get("max_num_of_trades_enabled"),
                    positions_info,
                    account.get("trading_window_enabled"),
                    account.get("trading_window_start_time"),
                    account.get("trading_window_end_time"),
                    account.get("user_time_zone"),
                    account.get("max_position_size"),
                    account.get("max_position_size_enabled"),  # New parameters
                )
            )

            if close_all_positions:
                logger.info("Trading condition met. Closing all positions.")
                close_positions(access_token, acc_num, env, positions_info)
            elif positions_to_close:
                logger.info(
                    f"Closing specific positions: {[p['id'] for p in positions_to_close]}"
                )
                close_positions(access_token, acc_num, env, positions_to_close)
            else:
                logger.info("No trading conditions met. No positions closed.")
        else:
            logger.error("Failed to fetch account equity. No update will be sent.")

        # Loop interval to prevent hitting rate limits
        time.sleep(5)  # Adjust as needed to stay within overall rate limits


if __name__ == "__main__":
    main()
