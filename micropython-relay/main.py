# main.py
# Simple REST API server for Raspberry Pi Pico W to control a relay
# Includes device registration, configurable name, periodic re-registration,
# consolidated payload, and memory optimization strategies.
# Uses the built-in 'socket' library (no external frameworks)

import network
import socket
import time
import machine
import ujson # For creating JSON responses
import gc    # Import garbage collector interface

# --- Configuration ---
# IMPORTANT: Replace with your actual WiFi credentials
WIFI_SSID = ""
WIFI_PASSWORD = ""

# --- Device Configuration ---
# IMPORTANT: Set a unique name for this device
DEVICE_NAME = "" # Example device name
DEVICE_TYPE = "" # Define device type
# IMPORTANT: Set the GPIO pin number connected to your relay's control pin
RELAY_PIN_NUMBER = 15  # Example: GP15

# Web server configuration
SERVER_PORT = 80 # Port 80 is the standard HTTP port

# Relay configuration (adjust if your relay is active LOW)
# Active HIGH: ON = 1, OFF = 0
# Active LOW:  ON = 0, OFF = 1
RELAY_ON_VALUE = 1
RELAY_OFF_VALUE = 0

# --- IoT Hub Configuration ---
# IMPORTANT: Replace with your IoT Hub's IP address or hostname
HUB_IP_ADDRESS = ""
HUB_PORT = 80 # Default HTTP port for the hub
HUB_REGISTER_PATH = "/device/register" # API endpoint path on the hub
REGISTRATION_TIMEOUT_S = 10 # Seconds to wait for registration connection/response
REGISTRATION_PERIOD_MS = 1000 * 60 * 5 # How often to check if re-registration is needed (e.g., 300000ms = 5 minutes)
WIFI_RECONNECT_MAX_ATTEMPTS = 3 # Maximum number of reconnection attempts before giving up

# --- Global State ---
ip_address = 'Not Connected' # Placeholder for Pico's IP address
is_registered = False # Flag to track registration status with the hub
pending_registration_check = False # Flag set by timer, checked in main loop
pending_wifi_check = False # Flag to check WiFi connectivity
timer = machine.Timer() # Hardware timer for periodic tasks

# --- Hardware Setup ---
# Configure the specified GPIO pin as an output
# Set the initial state to OFF
try:
    relay_pin = machine.Pin(RELAY_PIN_NUMBER, machine.Pin.OUT)
    relay_pin.value(RELAY_OFF_VALUE) # Start with the relay OFF
    print(f"Relay pin {RELAY_PIN_NUMBER} initialized. Initial state: OFF")
except Exception as e:
    print(f"Error initializing GPIO pin {RELAY_PIN_NUMBER}: {e}")
    print("Please check the RELAY_PIN_NUMBER setting.")
    # Optional: halt execution if pin setup fails critically
    # raise SystemExit # Or machine.reset()

# --- WiFi Connection ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True) # Activate the WiFi station interface

def connect_wifi():
    """Attempts to connect to the configured WiFi network."""
    global ip_address
    if wlan.isconnected():
        print("Already connected to WiFi.")
        ip_address = wlan.ifconfig()[0]
        return True

    print(f"Attempting to connect to SSID: {WIFI_SSID}...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    # Wait for connection with a timeout
    max_wait_seconds = 20
    start_time = time.ticks_ms()
    while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start_time) < max_wait_seconds * 1000:
        print('.', end='')
        time.sleep(1)

    if wlan.isconnected():
        status = wlan.ifconfig()
        ip_address = status[0] # Update global IP address
        print(f"\nConnected to WiFi successfully!")
        print(f"Pico W IP Address: {ip_address}")
        gc.collect() # Collect garbage after successful connection
        return True
    else:
        print("\nWiFi connection failed.")
        ip_address = 'Connection Failed'
        wlan.disconnect() # Ensure disconnected state
        return False

def check_wifi_connection():
    """Checks if WiFi is connected and attempts to reconnect if not."""
    global ip_address
    
    if wlan.isconnected():
        # WiFi is connected, update IP address in case it changed
        current_ip = wlan.ifconfig()[0]
        if ip_address != current_ip:
            print(f"IP address changed from {ip_address} to {current_ip}")
            ip_address = current_ip
        return True
    
    print("WiFi connection lost, attempting to reconnect...")
    # WiFi is not connected, try to reconnect
    attempts = 0
    while attempts < WIFI_RECONNECT_MAX_ATTEMPTS and not wlan.isconnected():
        attempts += 1
        print(f"Reconnection attempt {attempts}/{WIFI_RECONNECT_MAX_ATTEMPTS}...")
        
        # Ensure we're disconnected before trying to connect again
        try:
            wlan.disconnect()
            time.sleep(1)
        except:
            pass
            
        # Try to reconnect
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
            
            # Wait for connection with timeout
            wait_count = 0
            while not wlan.isconnected() and wait_count < 10:  # 10 seconds timeout
                print('.', end='')
                time.sleep(1)
                wait_count += 1
                
            if wlan.isconnected():
                status = wlan.ifconfig()
                ip_address = status[0]
                print(f"\nReconnected to WiFi successfully!")
                print(f"New IP Address: {ip_address}")
                return True
        except Exception as e:
            print(f"Reconnection error: {e}")
    
    if not wlan.isconnected():
        print("Failed to reconnect to WiFi after multiple attempts.")
        ip_address = 'Connection Failed'
        return False
    
    return wlan.isconnected()

# --- Payload Generation Helper ---
def get_device_payload():
    """Constructs the standardized payload dictionary for status and registration."""
    global is_registered # Access global flag
    global ip_address    # Access global IP
    global relay_pin     # Access relay pin object
    global wlan          # Access WLAN object
    global HUB_IP_ADDRESS # Access hub IP address

    # Collect garbage before potentially large payload creation
    gc.collect()

    try:
        current_pin_value = relay_pin.value()
        if current_pin_value == RELAY_ON_VALUE:
            current_relay_state = "ON"
        elif current_pin_value == RELAY_OFF_VALUE:
            current_relay_state = "OFF"
        else:
            current_relay_state = "Unknown"

        wifi_connected_status = wlan.isconnected()

        payload = {
            "device_name": DEVICE_NAME,
            "device_type": DEVICE_TYPE, # Added device type
            "relay_pin": RELAY_PIN_NUMBER,
            "relay_state": current_relay_state,
            "pin_value": current_pin_value,
            "ip_address": ip_address if wifi_connected_status else "N/A", # Use current IP or N/A
            "wifi_connected": wifi_connected_status,
            "wifi_ssid": WIFI_SSID if wifi_connected_status else None,
            "hub_registered": is_registered,
            "hub_ip_address": HUB_IP_ADDRESS, # Added hub IP address
            "mem_free": gc.mem_free() # Add free memory info for debugging
        }
        return payload
    except Exception as e:
        print(f"Error generating device payload: {e}")
        # Return a minimal error payload
        return {
            "device_name": DEVICE_NAME,
            "device_type": DEVICE_TYPE,
            "error": "Failed to generate full payload",
            "ip_address": ip_address,
            "wifi_connected": wlan.isconnected(),
            "hub_registered": is_registered,
            "hub_ip_address": HUB_IP_ADDRESS, # Added hub IP address
            "mem_free": gc.mem_free() # Add free memory info
        }


# --- Device Registration Function ---
def register_device(hub_ip, hub_port, path, payload_dict):
    """Attempts to register the device with the IoT Hub via HTTP POST using the provided payload. Updates global is_registered flag."""
    global is_registered # Declare intent to modify global variable
    device_name = payload_dict.get('device_name', 'N/A')
    print(f"Attempting registration for device '{device_name}' with hub at {hub_ip}:{hub_port}{path}...")
    client_socket = None  # Initialize variable
    success = False

    # Collect garbage before attempting network allocation
    gc.collect()
    print(f"Mem Free before registration attempt: {gc.mem_free()}")

    try:
        # Payload is now pre-generated, check if IP is valid before proceeding
        current_ip = payload_dict.get('ip_address', 'N/A')
        if current_ip == 'N/A' or current_ip == 'Not Connected' or current_ip == 'Connection Failed':
             print("Registration skipped: No valid IP address in payload.")
             is_registered = False # Ensure flag is false if skipped
             return False

        # Prepare payload JSON (might allocate memory)
        payload_json = ujson.dumps(payload_dict)
        payload_bytes = payload_json.encode('utf-8')

        # Construct HTTP POST request string (might allocate memory)
        request = f"POST {path} HTTP/1.0\r\n"
        request += f"Host: {hub_ip}\r\n"
        request += "Content-Type: application/json\r\n"
        request += f"Content-Length: {len(payload_bytes)}\r\n"
        request += "Connection: close\r\n\r\n"
        request_bytes = request.encode('utf-8') + payload_bytes

        # Get address info for the hub (might allocate memory)
        # Do this *before* creating the socket if possible
        addr_info = socket.getaddrinfo(hub_ip, hub_port)
        addr = addr_info[0][-1] # Use the first address returned

        # Create socket (can fail with ENOMEM)
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(REGISTRATION_TIMEOUT_S) # Set connection/read timeout

        # Connect (can fail)
        client_socket.connect(addr)
        print("Connected to hub.")

        # Send the request
        client_socket.sendall(request_bytes)
        print(f"Registration request sent with payload: {payload_json}")

        # Receive the response (allocates buffer)
        response_bytes = client_socket.recv(512) # Reduced buffer size slightly
        print("Received response from hub:")
        print("--- BEGIN HUB RESPONSE ---")
        print(response_bytes.decode('utf-8'))
        print("--- END HUB RESPONSE ---")

        # Check response status
        response_str = response_bytes.decode('utf-8', 'ignore')
        status_line = response_str.split('\r\n', 1)[0]
    
        if " 200 " in status_line or " 201 " in status_line or " 202 " in status_line:
            print("Registration successful (Hub responded with 2xx).")
            success = True
        else:
            print(f"Registration might have failed. Status line: '{status_line}'")
            success = False

    except OSError as e:
        print(f"Registration failed: Socket Error - {e}") # Will show ENOMEM here if it happens
        success = False
    except Exception as e:
        print(f"Registration failed: Unexpected Error - {e}")
        success = False
    finally:
        if client_socket:
            client_socket.close()
            print("Registration socket closed.")
        # Update global registration status only if an attempt was made (valid IP)
        if current_ip != 'N/A' and current_ip != 'Not Connected' and current_ip != 'Connection Failed':
            is_registered = success
            print(f"Registration status updated: is_registered = {is_registered}")
        # Collect garbage after network operation attempt
        gc.collect()
        print(f"Mem Free after registration attempt: {gc.mem_free()}")
        return success

# --- Periodic Registration Check (Timer Callback) ---
def periodic_registration_check(timer_instance):
    """Called periodically by the timer. Sets flags for registration and WiFi checks."""
    global is_registered
    global pending_registration_check # Flag to signal main loop for registration
    global pending_wifi_check # Flag to signal main loop for WiFi check

    # First, set flag for WiFi check regardless of registration status
    print("\n--- Timer: Setting flag for WiFi connectivity check. ---")
    pending_wifi_check = True
    
    # Set registration check flag if needed
    if not is_registered:
        print("--- Timer: Detected need for registration check. Setting flag. ---")
        pending_registration_check = True


# --- HTTP Response Helper ---
def send_response(client_socket, status_code, content_type, body):
    """Constructs and sends an HTTP response to the client."""
    response_str = None # Ensure variable exists for finally block
    try:
        status_message = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed", 500: "Internal Server Error"}.get(status_code, "OK")
        # Use byte strings where possible to potentially reduce intermediate string objects
        status_line = f"HTTP/1.0 {status_code} {status_message}\r\n".encode('utf-8')
        headers = f"Content-Type: {content_type}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode('utf-8')
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body # Assume body is string or already bytes

        client_socket.sendall(status_line)
        client_socket.sendall(headers)
        client_socket.sendall(body_bytes)

    except OSError as e:
        print(f"Error sending response: {e}")
    except Exception as e:
         print(f"Unexpected error in send_response: {e}")
    finally:
        # Ensure the client connection is always closed after sending
        if client_socket and not getattr(client_socket, '_closed', True):
            client_socket.close()
            # print("Client connection closed.") # Less verbose


# --- Request Handler Functions ---
# (Keep handle_relay_on, handle_relay_off, handle_index as they were in the previous version)
# ... [handle_relay_on, handle_relay_off definitions remain unchanged] ...
def handle_relay_on():
    """Turns the relay ON and returns response body."""
    try:
        relay_pin.value(RELAY_ON_VALUE)
        print(f"Relay on Pin {RELAY_PIN_NUMBER} turned ON for device '{DEVICE_NAME}'")
        # Return simple success indicator, status endpoint gives full details
        response_data = {'status': 'success', 'relay_state': 'ON', 'device_name': DEVICE_NAME}
        return 200, 'application/json', ujson.dumps(response_data)
    except Exception as e:
        print(f"Error setting relay ON: {e}")
        error_data = {'status': 'error', 'message': str(e), 'device_name': DEVICE_NAME}
        return 500, 'application/json', ujson.dumps(error_data)

def handle_relay_off():
    """Turns the relay OFF and returns response body."""
    try:
        relay_pin.value(RELAY_OFF_VALUE)
        print(f"Relay on Pin {RELAY_PIN_NUMBER} turned OFF for device '{DEVICE_NAME}'")
        # Return simple success indicator, status endpoint gives full details
        response_data = {'status': 'success', 'relay_state': 'OFF', 'device_name': DEVICE_NAME}
        return 200, 'application/json', ujson.dumps(response_data)
    except Exception as e:
        print(f"Error setting relay OFF: {e}")
        error_data = {'status': 'error', 'message': str(e), 'device_name': DEVICE_NAME}
        return 500, 'application/json', ujson.dumps(error_data)

def handle_get_status():
    """Gets the current status using the helper function and returns response body."""
    try:
        # Use the helper function to get the standardized payload
        # Includes gc.collect() inside get_device_payload()
        status_data = get_device_payload()
        print(f"Reporting status for '{DEVICE_NAME}': {status_data}")
        # Check if payload generation itself had an error
        if "error" in status_data:
             return 500, 'application/json', ujson.dumps(status_data)
        else:
             return 200, 'application/json', ujson.dumps(status_data)
    except Exception as e:
        # This handles errors in the handle_get_status function itself,
        print(f"Error in handle_get_status: {e}")
        error_data = {'status': 'error', 'message': f'Error retrieving status: {e}', 'device_name': DEVICE_NAME}
        return 500, 'application/json', ujson.dumps(error_data)

def handle_index():
    """Generates the HTML index page content."""
    # Added device name to the HTML title and heading
    # Added registration status to the page
    # Added free memory display
    gc.collect() # Collect before getting memory info
    mem_free = gc.mem_free()
    reg_status_text = "Registered with Hub" if is_registered else "NOT Registered with Hub"
    wifi_status_text = "Connected" if wlan.isconnected() else "Disconnected"
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{DEVICE_NAME} - Pico W Relay Control</title></head>
<body>
<h1>{DEVICE_NAME} - Pico W Relay Control (Socket)</h1>
<p>Server is running on IP: {ip_address}</p>
<p>Relay connected to Pin: {RELAY_PIN_NUMBER}</p>
<p>WiFi Status: {wifi_status_text}</p>
<p>Hub Status: {reg_status_text}</p>
<p>Hub IP Address: {HUB_IP_ADDRESS}</p>
<p>Free Memory: {mem_free} bytes</p>
<h2>API Endpoints:</h2>
<ul>
    <li><a href="/relay/on" target="_blank">/relay/on</a> (Turn Relay ON)</li>
    <li><a href="/relay/off" target="_blank">/relay/off</a> (Turn Relay OFF)</li>
    <li><a href="/status" target="_blank">/status</a> (Get Current Status)</li>
    <li><a href="/register" target="_blank">/register</a> (Trigger Hub Registration)</li>
    <li><a href="/wifi/check" target="_blank">/wifi/check</a> (Force WiFi Check)</li>
    <li><code>POST /hub/set_ip</code> (Update Hub IP Address) - Requires JSON body: {{"hub_ip": "new.ip.address"}}</li>
</ul>
</body></html>"""
    return 200, 'text/html', html_content

def handle_set_hub_ip(request_body):
    """Updates the hub IP address based on JSON request body."""
    global HUB_IP_ADDRESS
    global is_registered
    
    try:
        # Parse JSON request body
        data = ujson.loads(request_body)
        
        # Check if the required field is present
        if 'hub_ip' not in data:
            return 400, 'application/json', ujson.dumps({
                'status': 'error',
                'message': 'Missing required field: hub_ip',
                'device_name': DEVICE_NAME
            })
        
        # Update the global HUB_IP_ADDRESS
        new_hub_ip = data['hub_ip']
        old_hub_ip = HUB_IP_ADDRESS
        HUB_IP_ADDRESS = new_hub_ip
        
        # Reset registration status since we changed the hub
        is_registered = False
        
        print(f"Hub IP updated from {old_hub_ip} to {new_hub_ip}")
        
        # Return success response
        return 200, 'application/json', ujson.dumps({
            'status': 'success',
            'message': f'Hub IP updated to {new_hub_ip}',
            'device_name': DEVICE_NAME,
            'old_hub_ip': old_hub_ip,
            'new_hub_ip': new_hub_ip
        })
    except ValueError:
        return 400, 'application/json', ujson.dumps({
            'status': 'error',
            'message': 'Invalid JSON in request body',
            'device_name': DEVICE_NAME
        })
    except Exception as e:
        print(f"Error updating hub IP: {e}")
        return 500, 'application/json', ujson.dumps({
            'status': 'error',
            'message': f'Error updating hub IP: {str(e)}',
            'device_name': DEVICE_NAME
        })

def handle_trigger_registration():
    """Manually triggers registration with the hub."""
    try:
        # Get current device payload
        payload = get_device_payload()
        
        # Attempt registration
        success = register_device(HUB_IP_ADDRESS, HUB_PORT, HUB_REGISTER_PATH, payload)
        
        if success:
            return 200, 'application/json', ujson.dumps({
                'status': 'success',
                'message': f'Successfully registered with hub at {HUB_IP_ADDRESS}',
                'device_name': DEVICE_NAME,
                'hub_ip': HUB_IP_ADDRESS
            })
        else:
            return 400, 'application/json', ujson.dumps({
                'status': 'error',
                'message': f'Failed to register with hub at {HUB_IP_ADDRESS}',
                'device_name': DEVICE_NAME,
                'hub_ip': HUB_IP_ADDRESS
            })
    except Exception as e:
        print(f"Error triggering registration: {e}")
        return 500, 'application/json', ujson.dumps({
            'status': 'error',
            'message': f'Error triggering registration: {str(e)}',
            'device_name': DEVICE_NAME
        })

def handle_wifi_check():
    """Manually triggers WiFi connectivity check."""
    try:
        was_connected = wlan.isconnected()
        if was_connected:
            status = "WiFi is currently connected"
            print(f"{status} - IP: {ip_address}")
        else:
            status = "WiFi is currently disconnected, attempting to reconnect"
            print(status)
        
        # Force a reconnection check
        reconnected = check_wifi_connection()
        
        if reconnected:
            if not was_connected:
                message = f"Successfully reconnected to WiFi. New IP: {ip_address}"
            else:
                message = f"WiFi connection verified. IP: {ip_address}"
            
            return 200, 'application/json', ujson.dumps({
                'status': 'success',
                'message': message,
                'device_name': DEVICE_NAME,
                'ip_address': ip_address,
                'was_connected': was_connected
            })
        else:
            return 400, 'application/json', ujson.dumps({
                'status': 'error',
                'message': 'Failed to establish WiFi connection',
                'device_name': DEVICE_NAME,
                'was_connected': was_connected
            })
    except Exception as e:
        print(f"Error checking WiFi: {e}")
        return 500, 'application/json', ujson.dumps({
            'status': 'error',
            'message': f'Error checking WiFi: {str(e)}',
            'device_name': DEVICE_NAME
        })


# --- Main Server Loop ---
def start_server():
    """Sets up the socket server and handles incoming connections."""
    global pending_registration_check # Allow modification
    global pending_wifi_check # Allow modification

    # Create a TCP/IP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_address = ('0.0.0.0', SERVER_PORT)
    try:
        server_socket.bind(server_address)
        server_socket.listen(5)
        print(f"Starting web server for device '{DEVICE_NAME}' on http://{ip_address}:{SERVER_PORT}")
    except OSError as e:
        print(f"Error binding or listening on socket: {e}")
        if server_socket: server_socket.close()
        return

    # --- Start Periodic Registration Timer ---
    try:
        # Timer now sets flags for both WiFi check and registration check
        timer.init(period=REGISTRATION_PERIOD_MS, mode=machine.Timer.PERIODIC, callback=periodic_registration_check)
        print(f"Periodic check timer started (every {REGISTRATION_PERIOD_MS / 1000} seconds).")
    except Exception as e:
         print(f"Error starting periodic timer: {e}")


    while True:
        client_conn = None
        
        # Check for pending WiFi check FIRST
        if pending_wifi_check:
            print("Processing pending WiFi check (from main loop)...")
            was_connected = wlan.isconnected()
            wifi_reconnected = check_wifi_connection()
            pending_wifi_check = False # Reset flag after attempt
            
            if not was_connected and wifi_reconnected:
                print("WiFi was reconnected successfully!")
                # Since we reconnected, we should also try to register
                pending_registration_check = True
            elif not wifi_reconnected:
                print("WiFi is still disconnected after check.")
                # Since WiFi is still down, don't try to register now
                pending_registration_check = False
            
            gc.collect()
        
        # Check for pending registration AFTER WiFi check (only if WiFi is connected)
        if pending_registration_check and wlan.isconnected():
            print("Processing pending registration check (from main loop)...")
            payload = get_device_payload()
            register_device(HUB_IP_ADDRESS, HUB_PORT, HUB_REGISTER_PATH, payload)
            pending_registration_check = False # Reset flag after attempt
            gc.collect() # Clean up after registration attempt
        
        try:
            # Make the socket non-blocking with a short timeout so we can check flags
            server_socket.settimeout(1.0)  # 1 second timeout
            
            try:
                # Wait for a connection
                client_conn, client_addr = server_socket.accept()
                client_conn.settimeout(10.0)
                print(f"\nConnection from: {client_addr}")
                
                # Receive request
                request_bytes = client_conn.recv(1024) # Consider if 1024 is always needed
                if not request_bytes:
                     print("Client disconnected before sending data.")
                     client_conn.close()
                     continue

                request_str = request_bytes.decode('utf-8')

                # --- Basic Request Parsing ---
                first_line = request_str.split('\r\n', 1)[0]
                parts = first_line.split()

                status_code = 404
                content_type = 'text/plain'
                body = 'Not Found' # Default response body

                if len(parts) >= 2:
                    method = parts[0]
                    path = parts[1]
                    print(f"Parsed Request: {method} {path}")

                    # --- Routing ---
                    if method == 'GET':
                        if path == '/relay/on':
                            status_code, content_type, body = handle_relay_on()
                        elif path == '/relay/off':
                            status_code, content_type, body = handle_relay_off()
                        elif path == '/status':
                            status_code, content_type, body = handle_get_status()
                        elif path == '/':
                            status_code, content_type, body = handle_index()
                        elif path == '/register':
                            status_code, content_type, body = handle_trigger_registration()
                        elif path == '/wifi/check':
                            status_code, content_type, body = handle_wifi_check()
                        else:
                            status_code = 404
                            body = 'Not Found'
                    elif method == 'POST':
                        if path == '/hub/set_ip':
                            # Extract the request body for POST requests
                            request_body = request_str.split('\r\n\r\n', 1)[1] if '\r\n\r\n' in request_str else ''
                            status_code, content_type, body = handle_set_hub_ip(request_body)
                        elif path == '/relay/on':
                            status_code, content_type, body = handle_relay_on()
                        elif path == '/relay/off':
                            status_code, content_type, body = handle_relay_off()
                        elif path == '/wifi/check':
                            status_code, content_type, body = handle_wifi_check()
                        else:
                            status_code = 404
                            body = 'Not Found'
                    else: # Method not allowed
                        status_code = 405
                        body = 'Method Not Allowed'
                else: # Malformed request
                    status_code = 400
                    body = 'Bad Request'
                    print("Malformed request line received.")

                # --- Send Response ---
                # Ensure body is JSON string if content_type is json
                if content_type == 'application/json' and isinstance(body, dict):
                     body = ujson.dumps(body)

                send_response(client_conn, status_code, content_type, body)
                client_conn = None # Indicate socket is closed by send_response

            except OSError as e:
                if str(e) == "115" or str(e) == "[Errno 11]":  # EAGAIN or EWOULDBLOCK
                    # No connection available, continue loop to check for pending tasks
                    continue
                elif str(e) == "110" or "[Errno 110]" in str(e):  # ETIMEDOUT
                    # Socket timeout is expected, silently continue the loop
                    continue
                else:
                    # Other socket error
                    print(f"Socket Error: {e}")
        
        except OSError as e:
            print(f"Socket Error during connection handling: {e}")
            if client_conn and not getattr(client_conn, '_closed', True):
                try: client_conn.close()
                except Exception: pass
        except KeyboardInterrupt:
             print("\nServer stopped by user (Ctrl+C).")
             break # Exit the main loop
        except Exception as e:
            print(f"An unexpected error occurred in main loop: {e}")
            # Attempt to send error response ONLY if connection is still open
            if client_conn and not getattr(client_conn, '_closed', True):
                 try:
                     # Check if headers already sent - This check is difficult here.
                     # Assume headers not sent if we are in this exception block early.
                     send_response(client_conn, 500, 'text/plain', 'Internal Server Error')
                     client_conn = None # Socket closed by send_response
                 except Exception as send_err:
                     print(f"Could not send error response: {send_err}")
                 finally: # Ensure close even if error sending fails
                     if client_conn and not getattr(client_conn, '_closed', True):
                         try: client_conn.close()
                         except Exception: pass
        finally:
             # Moved this check ONLY for after handling a request
             # The main check is now at the top of the loop
             if client_conn and not getattr(client_conn, '_closed', True):
                try: client_conn.close()
                except Exception: pass
             
             # Explicit garbage collection after handling request
             gc.collect()


    # --- Cleanup ---
    timer.deinit()
    print("Periodic timer stopped.")
    if server_socket:
        server_socket.close()
        print("Server socket closed.")


# --- Main Execution ---
if __name__ == "__main__":
    gc.collect() # Initial garbage collection
    print(f"--- Pico W Relay Server for '{DEVICE_NAME}' Starting ---")
    print(f"Initial Memory Free: {gc.mem_free()}")
    if connect_wifi(): # Attempt to connect to WiFi
        # --- Attempt Initial Registration ---
        initial_payload = get_device_payload()
        print(f"Generated initial payload: {initial_payload}")
        register_device(HUB_IP_ADDRESS, HUB_PORT, HUB_REGISTER_PATH, initial_payload)
        # Note: is_registered flag is set within register_device

        # --- Start Local Server and Periodic Check Timer ---
        start_server()
    else:
        print("Could not connect to WiFi. Server not started.")


