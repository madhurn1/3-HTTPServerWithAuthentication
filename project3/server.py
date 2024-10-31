import socket
import signal
import sys
import random

# Read a command line argument for the port where the server must run.
port = 8080
if len(sys.argv) > 1:
    port = int(sys.argv[1])
else:
    print("Using default port 8080")
hostname = socket.gethostname()

# Start a listening server socket on the port
sock = socket.socket()
sock.bind(('', port))
sock.listen(2)

### Contents of pages we will serve.
# Login form
login_form = """
   <form action = "http://%s" method = "post">
   Name: <input type = "text" name = "username">  <br/>
   Password: <input type = "text" name = "password" /> <br/>
   <input type = "submit" value = "Submit" />
   </form>
"""
# Default: Login page.
login_page = "<h1>Please login</h1>" + login_form
# Error page for bad credentials
bad_creds_page = "<h1>Bad user/pass! Try again</h1>" + login_form
# Successful logout
logout_page = "<h1>Logged out successfully</h1>" + login_form
# A part of the page that will be displayed after successful login or the presentation of a valid cookie
success_page = """
   <h1>Welcome!</h1>
   <form action="http://%s" method = "post">
   <input type = "hidden" name = "action" value = "logout" />
   <input type = "submit" value = "Click here to logout" />
   </form>
   <br/><br/>
   <h1>Your secret data is here:</h1>
"""

# Load user data
def load_users():
    users, secrets = {}, {}
    with open("passwords.txt", "r") as f:
        for line in f:
            username, password = line.strip().split()
            users[username] = password
    with open("secrets.txt", "r") as f:
        for line in f:
            username, secret = line.strip().split()
            secrets[username] = secret
    return users, secrets

# Read user credentials and secrets
users, secrets = load_users()
cookies = {}  # Dictionary to store cookies associated with authenticated users

#### Helper functions
# Printing.
def print_value(tag, value):
    print("Here is the", tag)
    print("\"\"\"")
    print(value)
    print("\"\"\"")
    print()

# Signal handler for graceful exit
def sigint_handler(sig, frame):
    print('Finishing up by closing listening socket...')
    sock.close()
    sys.exit(0)
# Register the signal handler
signal.signal(signal.SIGINT, sigint_handler)

# Parse entity body to retrieve form data
def parse_form_data(data):
    params = {}
    for pair in data.split('&'):
        if '=' in pair:
            key, value = pair.split('=')
            params[key] = value
    return params

# Parse the "Cookie" header to extract the token
def extract_token(cookie_header):
    cookies = cookie_header.split('; ')
    for cookie in cookies:
        if cookie.startswith("token="):
            return cookie.split('=')[1]
    return None

# Main app logic
while True:
    client, addr = sock.accept()
    req = client.recv(1024)

    # Split request headers and body
    header_body = req.decode().split('\r\n\r\n')
    headers = header_body[0]
    body = '' if len(header_body) == 1 else header_body[1]
    print_value('headers', headers)
    print_value('entity body', body)

    # Parse apart the headers
    request_lines = headers.splitlines()
    first_line = request_lines[0] if request_lines else ""
    method, path, _ = first_line.split(" ") if len(first_line.split(" ")) == 3 else (None, None, None)
    cookie = None
    for line in request_lines:
        if line.startswith("Cookie:"):
            cookie = extract_token(line.split(": ")[1])

    submit_hostport = "%s:%d" % (hostname, port)
    html_content_to_send = login_page % submit_hostport
    headers_to_send = ''

    # Logout case (E)
    if method == "POST" and "action=logout" in body:
        if cookie in cookies:
            del cookies[cookie]
        headers_to_send = 'Set-Cookie: token=; expires=Thu, 01 Jan 1970 00:00:00 GMT\r\n'
        html_content_to_send = logout_page % submit_hostport

    # Case C: Valid cookie present
    elif cookie and cookie in cookies:
        username = cookies[cookie]
        secret = secrets.get(username, "No secret available.")
        html_content_to_send = (success_page % submit_hostport) + secret

    # Case D: Invalid cookie present
    elif cookie and cookie not in cookies:
        html_content_to_send = bad_creds_page % submit_hostport

    # POST for username-password authentication
    elif method == "POST":
        form_data = parse_form_data(body)
        username = form_data.get("username")
        password = form_data.get("password")

        # Case A: Successful username-password authentication
        if username in users and users[username] == password:
            secret = secrets.get(username, "No secret available.")
            html_content_to_send = (success_page % submit_hostport) + secret
            rand_val = str(random.getrandbits(64))
            cookies[rand_val] = username
            headers_to_send = 'Set-Cookie: token=' + rand_val + '\r\n'

        # Case B: Failed authentication
        else:
            html_content_to_send = bad_creds_page % submit_hostport

    # Construct and send the final response
    response  = 'HTTP/1.1 200 OK\r\n'
    response += headers_to_send
    response += 'Content-Type: text/html\r\n\r\n'
    response += html_content_to_send
    print_value('response', response)    
    client.send(response.encode())
    client.close()
    
    print("Served one request/connection!")
    print()

# We will never actually get here.
# Close the listening socket
sock.close()
