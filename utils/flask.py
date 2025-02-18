from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timezone
import os

app = Flask(__name__)

# MySQL configuration
db_config = {
    "user": "admin",
    "password": "tQ55Nlgify2JGSnKwCAi",
    "host": "tradersimpulse-main.c78skiy68i07.us-east-1.rds.amazonaws.com",
    "database": "tradersimpulse",
}


def create_db_connection():
    """Creates and returns a connection to the MySQL database"""
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            print("Connected to MySQL Database")
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None


@app.route("/add", methods=["POST"])
def create_or_update_row():
    """Creates a new row or updates an existing row in the trading_accounts table based on unique_id"""
    data = request.json
    print("Received data:", data)  # Log incoming data for debugging

    # Extract fields from JSON data
    unique_id = data.get("unique_id")
    if not unique_id:
        return jsonify({"error": "unique_id is required"}), 400

    account_id = data.get("account_id")
    account_name = data.get("account_name")
    env = data.get("env")
    accNum = data.get("accNum")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expiry_time = data.get("expiry_time")
    initial_balance = data.get("initial_balance")
    equity_eod = data.get("equity_eod")
    equity_eow = data.get("equity_eow")
    trading_window_start_time = data.get("trading_window_start_time")
    trading_window_end_time = data.get("trading_window_end_time")
    user_time_zone = data.get("user_time_zone")
    daily_loss_limit = data.get("daily_loss_limit")
    daily_profit_target = data.get("daily_profit_target")
    weekly_profit_target = data.get("weekly_profit_target")
    max_overall_profit = data.get("max_overall_profit")
    max_num_of_trades = data.get("max_num_of_trades")
    user = data.get("user")
    max_position_size = data.get("max_position_size")  # New field

    # **Convert enabled flags to integers (0 or 1)**
    def convert_to_int(value):
        return 1 if str(value).lower() in ["true", "1"] else 0

    daily_loss_limit_enabled = convert_to_int(
        data.get("daily_loss_limit_enabled", False)
    )
    daily_profit_target_enabled = convert_to_int(
        data.get("daily_profit_target_enabled", False)
    )
    weekly_profit_target_enabled = convert_to_int(
        data.get("weekly_profit_target_enabled", False)
    )
    max_overall_profit_enabled = convert_to_int(
        data.get("max_overall_profit_enabled", False)
    )
    max_num_of_trades_enabled = convert_to_int(
        data.get("max_num_of_trades_enabled", False)
    )
    trading_window_enabled = convert_to_int(data.get("trading_window_enabled", False))
    max_position_size_enabled = convert_to_int(
        data.get("max_position_size_enabled", False)
    )  # New field

    # **Convert max_position_size to float**
    try:
        max_position_size = (
            float(max_position_size) if max_position_size is not None else 0.0
        )
    except (ValueError, TypeError):
        max_position_size = 0.0

    # Handle trading_window_enabled_since
    trading_window_enabled_since = None
    if trading_window_enabled == 1:
        trading_window_enabled_since = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # Log the converted enabled flags for debugging
    print(f"daily_loss_limit_enabled: {daily_loss_limit_enabled}")
    print(f"daily_profit_target_enabled: {daily_profit_target_enabled}")
    print(f"weekly_profit_target_enabled: {weekly_profit_target_enabled}")
    print(f"max_overall_profit_enabled: {max_overall_profit_enabled}")
    print(f"max_num_of_trades_enabled: {max_num_of_trades_enabled}")
    print(f"trading_window_enabled: {trading_window_enabled}")
    print(f"max_position_size_enabled: {max_position_size_enabled}")
    print(f"max_position_size: {max_position_size}")

    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()

        query = """
            INSERT INTO trading_accounts (
                unique_id, account_id, account_name, env, accNum, access_token, refresh_token, expiry_time,
                initial_balance, equity_eod, equity_eow, trading_window_start_time, trading_window_end_time,
                user_time_zone, daily_loss_limit, daily_loss_limit_enabled, daily_profit_target,
                daily_profit_target_enabled, weekly_profit_target, weekly_profit_target_enabled,
                max_overall_profit, max_overall_profit_enabled, max_num_of_trades, max_num_of_trades_enabled,
                trading_window_enabled, trading_window_enabled_since, user,
                max_position_size, max_position_size_enabled  -- New fields
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                account_name = VALUES(account_name),
                env = VALUES(env),
                accNum = VALUES(accNum),
                access_token = VALUES(access_token),
                refresh_token = VALUES(refresh_token),
                expiry_time = VALUES(expiry_time),
                initial_balance = VALUES(initial_balance),
                equity_eod = VALUES(equity_eod),
                equity_eow = VALUES(equity_eow),
                trading_window_start_time = VALUES(trading_window_start_time),
                trading_window_end_time = VALUES(trading_window_end_time),
                user_time_zone = VALUES(user_time_zone),
                daily_loss_limit = VALUES(daily_loss_limit),
                daily_loss_limit_enabled = VALUES(daily_loss_limit_enabled),
                daily_profit_target = VALUES(daily_profit_target),
                daily_profit_target_enabled = VALUES(daily_profit_target_enabled),
                weekly_profit_target = VALUES(weekly_profit_target),
                weekly_profit_target_enabled = VALUES(weekly_profit_target_enabled),
                max_overall_profit = VALUES(max_overall_profit),
                max_overall_profit_enabled = VALUES(max_overall_profit_enabled),
                max_num_of_trades = VALUES(max_num_of_trades),
                max_num_of_trades_enabled = VALUES(max_num_of_trades_enabled),
                trading_window_enabled = VALUES(trading_window_enabled),
                trading_window_enabled_since = VALUES(trading_window_enabled_since),
                user = VALUES(user),
                max_position_size = VALUES(max_position_size),
                max_position_size_enabled = VALUES(max_position_size_enabled)  -- New fields
        """

        cursor.execute(
            query,
            (
                unique_id,
                account_id,
                account_name,
                env,
                accNum,
                access_token,
                refresh_token,
                expiry_time,
                initial_balance,
                equity_eod,
                equity_eow,
                trading_window_start_time,
                trading_window_end_time,
                user_time_zone,
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
                trading_window_enabled,
                trading_window_enabled_since,
                user,
                max_position_size,
                max_position_size_enabled,  # New fields
            ),
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Row created or updated successfully!"})
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500


@app.route("/delete", methods=["POST"])
def delete_row():
    """Deletes a row from the trading_accounts table based on unique_id"""
    data = request.json
    unique_id = data.get("unique_id")  # Required to identify the row to delete

    if not unique_id:
        return jsonify({"error": "unique_id is required"}), 400

    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()

        query = "DELETE FROM trading_accounts WHERE unique_id = %s"
        cursor.execute(query, (unique_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"message": "Row deleted successfully!"})
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500


if __name__ == "__main__":
    app.run(debug=True)
