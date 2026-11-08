from socket import *
import os
import re
import threading


# ---------------------- Global Variables and Locks -------------------
PATTERN = re.compile(r"^[A-Za-z0-9~!@#$%^&*_\-+=`|\(){}\[\]:;\"'<>,.?/]+$")
credentials_file = "credentials.txt"   
commands_contents = ["CRT","MSG", "DLT", "EDT", "LST", 
                    "RDT", "UPD", "DWN", "RMV","XIT"]
file_exclude = {".DS_Store", "Thumbs.db", "desktop.ini", "ehthumbs.db"}

users = {}
threads = {}
active_users = set()
user_posts = {}
received_seqs = {} 
processed_seqs = {}

user_lock = threading.Lock()
active_lock = threading.Lock()
file_lock = threading.Lock() 
seq_lock = threading.Lock()
send_lock = threading.Lock()


# ----------------------- Instrumental Function -----------------------
### Load User Credentials File ###
def load_credentials(credentials_file):
    credentials = {}
    try:
        # Open and read credentials file
        with open(credentials_file, "r") as file:
            for line in file:
                clear_line = line.strip()
                if not clear_line:  # Skip empty lines
                    continue
                username, password = clear_line.split()
                credentials[username] = password
    except FileNotFoundError: # Doesn't exist, file should be created and then used for new user deposits
        open(credentials_file, "w").close()   
    return credentials


### Test password ###
def password_valid(password):
    return PATTERN.fullmatch(password) is not None
 

### Test user name ###
def username_valid(username):
    return PATTERN.fullmatch(username) is not None


### Test commands ### 
def commands_valid(commands,commands_contents):
    # commands=commands.split(' ').strip()
    print(commands)
    print(commands_contents)
    if str(commands) not in commands_contents:
        return False
    return True


### Send ACK to client ###
def send_ack(udp_socket, seq, message, client_address):
    ack_message = f"ACK|{seq}|{message}"
    safe_sendto(udp_socket,ack_message, client_address)


### Send message to client with thread-safe UDP socket ###
def safe_sendto(sock, message, addr):
    with send_lock:
        sock.sendto(message.encode(), addr)
    

### Verify the existence of the file ###
def UPD_CONFIRM( commands, udp_socket, client_address, seq):
    thread_title = commands[1]
    filename = commands[2]
    target_file = f"{thread_title}-{filename}"
    if os.path.exists(target_file):
        message = f"{filename} successfully uploaded to {thread_title} thread"
    else:
        message = f"{filename} failed to be upload to {thread_title} thread. please try again"

    ack_message = f"ACK|{seq}|{message}"
    safe_sendto(udp_socket,ack_message, client_address)


# ----------------------- Discussion Forum Operations -----------------------
### CRT ### 
# Create a new discussion thread
def handle_CRT(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) != 2:
        safe_sendto(udp_socket,f"ACK|{seq}|Incorrect syntax for CRT", client_address)
        return
    
    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]
    print(f"{username} issued {commands_cont} command")

    with seq_lock:
        processed_seqs[username].add(seq)

    if os.path.exists(thread_title):  # If the file exists, send an "already exists" message and return
        print(f'Thread {thread_title} exists')
        safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} exists", client_address)
    else:                           # If the file does not exist, print a message and create the file
        print(f'Thread {thread_title} created')
        with open(thread_title, "w") as f:
            f.write(f"{username}\n")
        safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} created", client_address)


### XIT ### 
#  Exiting the program       
def handle_XIT(username, commands, udp_socket, client_address,seq):
    if len(commands) != 1:
            safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for XIT", client_address)
            return
    with active_lock:
        active_users.discard(username)
    print(f"{username} exited")
    print("Waiting for clients")
    safe_sendto(udp_socket,f"ACK|{seq}|Goodbye", client_address)


### MSG ### 
# Post a message to a thread
def handle_MSG(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) < 3:
        safe_sendto(udp_socket,f"ACK|{seq}|Incorrect syntax for MSG", client_address)
        return

    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]
    message = ' '.join(commands[2:])
    print(f"{username} issued {commands_cont} command")

    with file_lock:
        if not os.path.exists(thread_title):
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return
        

        with open(thread_title, "r+") as file:
            lines = file.readlines()
            msg_num = 1
            for line in lines:
                parts = line.strip().split()
                if parts[0].isdigit()and parts:
                    msg_num += 1

            lines.append(f"{msg_num} {username}: {message}\n")
            file.seek(0)
            file.writelines(lines)
    with seq_lock:
        processed_seqs[username].add(seq)

    print(f"{username} posted to {thread_title} thread")
    safe_sendto(udp_socket,f"ACK|{seq}|Message posted to {thread_title} thread", client_address)


### LST ### 
# List all active discussion threads
def handle_LST(username, commands,udp_socket, client_address, commands_cont,seq):

    if len(commands) > 1:
        safe_sendto(udp_socket,f"ACK|{seq}|Incorrect syntax for LST", client_address)
        return

    files = []
    threads = []
    print(f"{username} issued {commands_cont} command")

    for f in os.listdir():
        if os.path.isfile(f):
            files.append(f)

    for t in files:
        if not t.endswith(".txt") and t not in file_exclude and not t.endswith(".py") and not t.endswith(".pdf") and not t.endswith(".exe") and '-' not in t:
            threads.append(t)

    if threads:
        safe_sendto(udp_socket,(f"ACK|{seq}|The list of active threads:\n" + "\n".join(threads)), client_address)
    else:
        safe_sendto(udp_socket,f"ACK|{seq}|No threads to list", client_address)


### RDT ### 
# Read the contents of a thread
def handle_RDT(username, commands, udp_socket, client_address, commands_cont,seq):
    if len(commands) != 2:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for RDT", client_address)
        return

    thread_title = commands[1]

    print(f"{username} issued {commands_cont} command")

    # File does not exist
    if not os.path.exists(thread_title):
        print(f"Incorrect thread specified")
        safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
        return
    
    # File does not exist
    with open(thread_title, "r") as f:
        lines = f.readlines()[1:]  # skip creator line


    if not lines:                                        # Empty document
        print(f"Thread {thread_title} read")
        safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} is empty", client_address)
    else:
        print(f"Thread {thread_title} read")
        cleaned_lines = [line.strip() for line in lines]
        formatted = "\n".join(cleaned_lines)
        safe_sendto(udp_socket,f'ACK|{seq}|{formatted}', client_address)


### DLT ### 
# Delete a message from a thread
# Message cannot be deleted in the following cases: 
#       (1) thread file missing, 
#       (2) message number invalid, 
#       (3) not posted by the current user
def handle_DLT(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) != 3:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for DLT", client_address)
        return
    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]
    msg_number = commands[2]
    msg_number_list = []

    print(f"{username} issued {commands_cont} command")

    with file_lock:
        if not os.path.exists(thread_title):
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return

        with open(thread_title, "r") as f:
            lines = f.readlines()

        new_lines = [lines[0]]  # Keep the first line: the creator's username
        deleted = False

        for line in lines[1:]:
            parts = line.strip().split()
            msg_number_list.append(str(parts[0]))
            if parts and parts[0] == msg_number and parts[1].startswith(username + ":"):
                deleted = True
                continue  # Skip this line to achieve the effect of deletion
            else:
                new_lines.append(line)

        if not deleted:
            print('Message cannot be deleted') 
            if str(msg_number) not in msg_number_list:
                safe_sendto(udp_socket,f"ACK|{seq}|This message number does not exist", client_address)
            else:
                safe_sendto(udp_socket,f"ACK|{seq}|The message belongs to another user and cannot be edited", client_address)
            return

        # Renumber and rewrite messages to the file
        with open(thread_title, "w") as file:
            file.write(lines[0])  # Rewrite the creator's username to the first line
            count = 1
            for line in new_lines[1:]:
                if line.strip() and ':' in line:
                    content = ' '.join(line.strip().split()[1:])
                    file.write(f"{count} {content}\n")
                    count += 1
                else:
                    file.write(line)  
    with seq_lock:
        processed_seqs[username].add(seq)
    print('The message has been deleted')
    safe_sendto(udp_socket,f"ACK|{seq}|The message has been deleted", client_address)


### EDT ### 
# Edit a message in a thread
# ”EDT 3331 2 I PWNED Networks exam“
# Message cannot be edited if: 
#   (1) thread file is missing,
#   (2) message number is invalid or not owned by the user,
#   (3) new content is missing or unchanged
def handle_EDT(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) < 4:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for EDT", client_address)
        return

    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]
    msg_number = commands[2]
    new_msg = ' '.join(commands[3:])

    print(f"{username} issued {commands_cont} command")

    with file_lock:
        if not os.path.exists(thread_title):
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return

        with open(thread_title, "r") as file:
            lines = file.readlines()

        edited = False
        for i in range(1, len(lines)):
            parts = lines[i].strip().split()
            if parts and parts[0] == msg_number and parts[1].startswith(username + ":"):
                lines[i] = f"{msg_number} {username}: {new_msg}\n"
                edited = True
                break

        if not edited:
            print("Message cannot be edited")
            safe_sendto(udp_socket,f"ACK|{seq}|The message belongs to another user and cannot be edited", client_address)
            return

        with open(thread_title, "w") as file:
            file.writelines(lines)
    with seq_lock:
        processed_seqs[username].add(seq)

    print("Message has been edited")
    safe_sendto(udp_socket,f"ACK|{seq}|Message has been edited", client_address)


### RMV ### 
# Remove an entire thread (by its creator)
def handle_RMV(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) != 2:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for RMV", client_address)
        return
    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]

    print(f"{username} issued {commands_cont} command")

    with file_lock:
        if not os.path.exists(thread_title):
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return

        with open(thread_title, "r") as f:
            creator = f.readline().strip()

        if creator != username:
            print(f"Thread {thread_title} cannot be removed")
            safe_sendto(udp_socket,f"ACK|{seq}|The thread was created by another user and cannot be removed", client_address)
            return

        os.remove(thread_title)
        for file in os.listdir():
            if file.startswith(thread_title + "-"):
                os.remove(file)

    with seq_lock:
        processed_seqs[username].add(seq)
    print(f"Thread {thread_title} removed")
    safe_sendto(udp_socket,f"ACK|{seq}|The Thread has been removed", client_address)


### UPD ### 
# Upload a file to a thread (via TCP)
# ‘UPD 3331 test.exe’
def handle_UPD(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) != 3:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for UPD", client_address)
        return
    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title = commands[1]
    filename = commands[2]
    new_filename = f"{thread_title}-{filename}"

    print(f"{username} issued {commands_cont} command")

    with file_lock:
    # Check if the thread exists
        if not os.path.exists(thread_title):
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return
        
        if os.path.exists(new_filename):
            safe_sendto(udp_socket,f"ACK|{seq}|{filename} already exists in {thread_title} thread. Please rename and try again.", client_address)
            return

    # Create a TCP socket to receive the file
    tcp_socket = socket(AF_INET, SOCK_STREAM)
    tcp_socket.bind(('', 0)) # Bind to an available port automatically assigned by the OS
    assigned_port = tcp_socket.getsockname()[1]
    tcp_socket.listen(5)
    safe_sendto(udp_socket,f"ACK|{seq}|{assigned_port}/READY_TO_RECEIVE", client_address)
    conn, addr = tcp_socket.accept()

    with file_lock:
        with open(new_filename, "wb") as f:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                f.write(data)

    conn.close()
    tcp_socket.close()

    # Add a file upload record to the thread
    with file_lock:
        with open(thread_title, "a") as f:
            f.write(f"{username} uploaded {filename}\n")

    with seq_lock:
        processed_seqs[username].add(seq)

    if os.path.exists(new_filename):
        message = f"{filename} uploaded to {thread_title} thread"
        print(f"{username} uploaded file {filename} to {thread_title} thread")
    else:
        message = f"{filename} failed to be uploaded. Please try again"
        print(f"{username} failed to uploaded {filename} to {thread_title} thread")

    safe_sendto(udp_socket,f"ACK|{seq}|{message}", client_address)


### DWN ### 
# Download a file from a thread (via TCP)
def handle_DWN(username, commands, udp_socket, client_address, commands_cont,seq):
    global processed_seqs
    if len(commands) != 3:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid syntax for DWN", client_address)
        return
    with seq_lock:
        if username not in processed_seqs:
            processed_seqs[username] = set()
        if seq in processed_seqs[username]:
            safe_sendto(udp_socket, f"ACK|{seq}|[$DUPLICATE$]", client_address)
            return

    thread_title= commands[1]
    filename = commands[2]
    target_file = f"{thread_title}-{filename}"

    print(f"{username} issued {commands_cont} command")

    with file_lock:
        if not os.path.exists(thread_title):
            print(f"{filename} does not exist in Thread {thread_title}")
            safe_sendto(udp_socket,f"ACK|{seq}|Thread {thread_title} does not exist", client_address)
            return

        if not os.path.exists(target_file):
            print(f"{filename} does not exist in Thread {thread_title}")
            safe_sendto(udp_socket,f"ACK|{seq}|File does not exist in Thread {thread_title}", client_address)
            return

    # Create a TCP socket to send the file
    tcp_socket = socket(AF_INET, SOCK_STREAM)
    tcp_socket.bind(('', 0))   # Bind to an available port automatically assigned by the OS
    assigned_port = tcp_socket.getsockname()[1]
    tcp_socket.listen(5)
    safe_sendto(udp_socket,f"ACK|{seq}|{assigned_port}/READY_TO_SEND", client_address)
    conn, addr = tcp_socket.accept()

    with file_lock:
        with open(target_file, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                conn.sendall(chunk)

    conn.close()
    tcp_socket.close()
    with seq_lock:
        processed_seqs[username].add(seq)

    print(f"{filename} downloaded from Thread {thread_title}")


# ----------------------- Authenticate -----------------------
def authenticate_user(response, users, active_users, udp_socket, client_address,seq):
    # if is_duplicate_seq(client_address, int(seq)):
    #     send_ack(udp_socket, seq, "DUPLICATE", client_address)
    #     return

    input_name = response.replace("/USER", "").strip()
    print(f"Client authenticating")

    with active_lock:
        if input_name in active_users:          # User is already logged in
            print(f'{input_name} has already logged in')
            response = f"ACK|{seq}|{input_name}/LOGGED/AUTHENTICATE"
            safe_sendto(udp_socket,response, client_address)
            return
    
    with user_lock:
        if input_name in users.keys():          # User is already registered; ask for password
            response = f"ACK|{seq}|{input_name}/PASSWORD/AUTHENTICATE"
        else:                                   # New user registration
            response = f"ACK|{seq}|{input_name}/NEWUSER/PASSWORD/AUTHENTICATE"
        
        safe_sendto(udp_socket,response, client_address)


def authenticate_password(response, users, active_users, udp_socket, client_address,seq):
    response = response.replace("/PASSWORD", "").strip()
    parts = response.split("/middle_gap/")
    
    # Invalid password format; notify the client
    if len(parts) < 2:
        print(f"Invalid password format for {username}") 
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid password/FORMAT/PASSWORD/AUTHENTICATE", client_address)
        return  # Return and do not save passwords
    
    username, password = parts[0].strip(), parts[1].strip()

    # Stored new users
    if password.endswith("/NEWUSER"):

        # print(f'password is {password}') ### Print for solving problems
        password = password.replace('/NEWUSER','')

        if not username_valid(username):
            print(f"Invalid username format for {username}") 
            safe_sendto(udp_socket,f"ACK|{seq}|Invalid username/FORMAT/PASSWORD/AUTHENTICATE", client_address)
            return  # Return and do not save passwords

        # Wrong password format
        if not password_valid(password):
            print(f"Invalid password format for {username}") 
            safe_sendto(udp_socket,f"ACK|{seq}|Invalid password/FORMAT/PASSWORD/AUTHENTICATE", client_address)
            return  # Return and do not save passwords

        # print((username, password)) ### Print for solving problems

        print(f'New user')
        print(f'{username} successfully logged in')

        with user_lock:
            users[username] = password
            with open(credentials_file, "a") as file:  # ‘new_user+passwords is written into file’
                file.write(f"\n{username} {password}")

        with active_lock:
            active_users.add(username)

        response = f"ACK|{seq}|{username}/NEWUSER/SUCCESS/PASSWORD/AUTHENTICATE"
        safe_sendto(udp_socket,response, client_address)
             
    else:
        with user_lock:
            # Correct Password
            if username in users and users[username] == password: 
                print(f'{username} successful login') 
                active_users.add(username)
                response = f"ACK|{seq}|{username}/SUCCESS/PASSWORD/AUTHENTICATE"
        
            # Incorrect Password
            else:  
                print(f'Incorrect password')
                response = f"ACK|{seq}|Invalid password/PASSWORD/AUTHENTICATE"

            safe_sendto(udp_socket,response, client_address)
        

# ----------------------- Forum Section -----------------------
def forum_operations(response, active_users, udp_socket, client_address, tcp_port,seq):
    response = response.replace('/FORUM', "").strip()
    parts = response.split("/middle_gap/")

    if len(parts) < 2:
        print(f"Invalid commands format for {username}") 
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid commands/COMMANDS/FORUM", client_address)
        return  
    
    username, commands = parts[0].strip(), parts[1].strip()
    commands = [c for c in commands.strip().split(" ") if c]
    commands_cont = commands[0] if commands else ""

    if username.endswith("/USER"):
        username = username.replace("/USER","")

    if commands_cont == "CRT":
        handle_CRT(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "LST":
        handle_LST(username,commands,udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "MSG":
        handle_MSG(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "RDT":
        handle_RDT(username,commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "DLT":
        handle_DLT(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "EDT":
        handle_EDT(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "RMV":
        handle_RMV(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "XIT":
        handle_XIT(username, commands, udp_socket, client_address,seq)
    elif commands_cont == "UPD":
        handle_UPD(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "DWN":
        handle_DWN(username, commands, udp_socket, client_address, commands_cont,seq)
    elif commands_cont == "UPD_CONFIRM":
        UPD_CONFIRM( commands, udp_socket, client_address, seq)
    else:
        safe_sendto(udp_socket,f"ACK|{seq}|Invalid command. Please try again.", client_address)


def handle_client(udp_connection, udp_socket, client_address,tcp_port,users):
    global active_users
    try:
        response = udp_connection.decode()

        parts = response.split("|", 2)
        if len(parts) != 3:
            print(f"Malformed message from {client_address}: {response}")
            return

        prefix, seq, response_from_client = parts

        if prefix != "SEQ" or not seq.isdigit():
            print(f"Malformed message from {client_address}: {response}")
            return

        if response_from_client.endswith("/USER"):
            authenticate_user(response_from_client, users, active_users, udp_socket, client_address,seq)

        elif response_from_client.endswith("/PASSWORD"):
            authenticate_password(response_from_client, users, active_users,udp_socket, client_address,seq)

        elif response_from_client.endswith("/FORUM"):
            forum_operations(response_from_client,active_users, udp_socket, client_address, tcp_port,seq)
    
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")


# ----------------------- Start the Server -----------------------
def start_server(port):
    udp_socket = socket(AF_INET, SOCK_DGRAM)
    udp_socket.bind(('', port))
    tcp_port = port + 1
    print(f">java Server {port}")
    print(f"Waiting for clients")

    while True:
        try:
            users = load_credentials(credentials_file)
            udp_connection, udp_addr = udp_socket.recvfrom(1024)

            thread = threading.Thread(target=handle_client, args=(udp_connection, udp_socket, udp_addr, tcp_port,users))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print("[Error receiving packet]", e)


# ----------------------- Main Function -----------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Enter: python3 server.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])
    start_server(port)