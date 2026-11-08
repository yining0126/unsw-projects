import socket
import os
import time
import sys
import random
import threading

seq_counter = random.randint(999, 9999)
seq_counter_lock = threading.Lock()


# ----------------------- Instrumental Function -----------------------
def udp_send_with_seq(udp_socket, message, addr, expected_prefix="ACK", timeout=1.0, max_retries=5):
    global seq_counter, seq_response_cache
    with seq_counter_lock:
        seq = seq_counter
        seq_counter += 1
    seq_message = f"SEQ|{seq}|{message}"

    for attempt in range(1, max_retries + 1):
        try:
            udp_socket.sendto(seq_message.encode(), addr)
            udp_socket.settimeout(timeout)

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response, _ = udp_socket.recvfrom(2048)
                    decoded = response.decode(errors="replace").strip()

                    if decoded.startswith(f"{expected_prefix}|{seq}|"):
                        payload = decoded.split("|", 2)[2]
                        if payload == '[$DUPLICATE$]':
                            return "Command executed successfully"
                        return payload 

                    else:
                        continue

                except socket.timeout:
                    break  

            print(f"[Retry {attempt}] Timeout waiting for ACK SEQ {seq}\n[Warning] SEQ {seq} might be lost, retransmitting...")

        except Exception as e:
            print(f"[Error] during UDP send SEQ {seq}: {e}")

    print(f"[Fail] SEQ {seq} failed after {max_retries} retries.")
    return "Packet Loss"


# ----------------------- Authenticate -----------------------
def authenticate_client(read_response, udp_socket, server_ip, port):
    if read_response == "Invalid password":
        print("Invalid password")
        return False

    elif read_response.endswith("/LOGGED"):
        read_response = read_response.replace("/LOGGED", "")
        print(f'{read_response} has already logged in')
        return False

    elif read_response.endswith("/PASSWORD"):
        read_response = read_response.replace("/PASSWORD", "")

        if not read_response.endswith("/NEWUSER"):
            name = read_response.strip()
            password = input("Enter password: ").strip()
        else:
            name = read_response.replace("/NEWUSER", "").strip()
            password = input("New user, enter password: ").strip()
            password += "/NEWUSER"

        password += "/PASSWORD"
        password_msg = f"{name}/middle_gap/{password}"

        while True:
            read_response = udp_send_with_seq(udp_socket, password_msg, (server_ip, port))

            if read_response == "Packet Loss":
                print("Silence from the server... Trying again!")
                continue
            elif read_response == "DUPLICATE":
                print("[Info] Duplicate ACK received: password command already processed.")
                return True

            read_response = read_response.replace('/PASSWORD/AUTHENTICATE', '')

            if read_response.endswith("/FORMAT"):
                print("Invalid password format")
                break
            elif read_response == "Invalid username":
                print("Invalid username")
                break
            elif read_response == "Invalid password":
                print("Invalid password")
                break
            elif read_response.endswith("/SUCCESS"):
                username = read_response.replace("/SUCCESS", "").strip()
                if not username.endswith("/NEWUSER"):
                    print("Welcome to the forum")
                return True

    return False


# ----------------------- Upload and Download File -----------------------
def client_upload_file(udp_socket, server_ip, udp_port, username, thread_title, filename):
    # # DBug Print
    # print(f'client Upload filename: {filename}')
    
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return
    
    command = f"{username}/middle_gap/UPD {thread_title} {filename}/FORUM"
    response = udp_send_with_seq(udp_socket, command, (server_ip, udp_port))

    if "Packet Loss" in response:
        print("Upload initiation failed: no response from server.")
        return

    if "/READY_TO_RECEIVE" not in response:
        print(response)
        return

    try:
        tcp_port = int(response.split("/")[0])
    except ValueError:
        print("Invalid TCP port received from server.")
        return

    time.sleep(0.7)
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((server_ip, tcp_port))
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            tcp_socket.sendall(chunk)
    tcp_socket.close()

    # Confirm upload result with UDP
    confirm_msg = f"{username}/middle_gap/UPD_CONFIRM {thread_title} {filename}/FORUM"
    response = udp_send_with_seq(udp_socket, confirm_msg, (server_ip, udp_port))
    print(response)


def client_download_file(udp_socket, server_ip, udp_port, username, thread_title, filename):
    command = f"{username}/middle_gap/DWN {thread_title} {filename}/FORUM"
    response = udp_send_with_seq(udp_socket, command, (server_ip, udp_port))

    if "Packet Loss" in response:
        print("Download initiation failed: no response from server.")
        return
    
    if "/READY_TO_SEND" not in response:
        print(response)
        return

    try:
        tcp_port = int(response.split("/")[0])
    except ValueError:
        print("Invalid TCP port received from server.")
        return

    # Automatic renaming of existing files before downloading
    original_filename = filename
    counter = 1
    while os.path.exists(filename):
        name, ext = os.path.splitext(original_filename)
        filename = f"{name}({counter}){ext}"
        counter += 1

    time.sleep(0.7)
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((server_ip, tcp_port))
    with open(filename, "wb") as f:
        while True:
            chunk = tcp_socket.recv(4096)
            if not chunk:
                break
            f.write(chunk)
    tcp_socket.close()

    # Verify download successfully
    if os.path.exists(filename):
        message = f"{filename} successfully downloaded"
    else:
        message = f"{filename} failed to be downloaded. Please try again"

    print(message)


# ----------------------- Command Input Loop -----------------------
def command_loop(udp_socket, server_ip, port, username):
    while True:
        command_input = input("Enter one of the following commands: CRT, MSG, DLT, EDT, LST, RDT, UPD, DWN, RMV, XIT: ").strip()
        if not command_input:
            continue

        parts = command_input.strip().split()
        command_type = parts[0].upper()

        if command_type == "UPD" and len(parts) == 3:
            client_upload_file(udp_socket, server_ip, port, username, parts[1], parts[2])
            continue
        elif command_type == "DWN" and len(parts) == 3:
            client_download_file(udp_socket, server_ip, port, username, parts[1], parts[2])
            continue

        comm_msg = command_input + '/FORUM'
        command_response = udp_send_with_seq(udp_socket, f"{username}/middle_gap/{comm_msg}", (server_ip, port))

        if command_response == "Packet Loss":
            print("Silence from the server... Trying again!")
            continue

        else:
            print(command_response)
            if command_response == "Goodbye":
                udp_socket.close()
                sys.exit(0)


# ----------------------- Start the Client -----------------------
def start_client(server_ip, port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f">java Client {port}")

    while True:
        username = input("Enter username: ").strip()
        if not username:
            print("Username could not be empty. Please enter again.")
            continue

        msg = f"{username}/USER"
        read_response = udp_send_with_seq(udp_socket, msg, (server_ip, port))

        if read_response == "Packet Loss":
            print("Failed to get response from server. Try again.")
            continue
        
        elif read_response == "DUPLICATE":
            print("[Info] Duplicate USER request already processed.")
            continue

        if read_response.endswith("/AUTHENTICATE"):
            read_response = read_response.replace("/AUTHENTICATE", "")
            success = authenticate_client(read_response, udp_socket, server_ip, port)
            if success:
                command_loop(udp_socket, server_ip, port, username)
        elif read_response.endswith("/FORUM"):
            read_response = read_response.replace("/FORUM", "")
            command_loop(udp_socket, server_ip, port, username)


# ----------------------- Main Function -----------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 client.py <server_port>")
        sys.exit(1)

    server_ip = "127.0.0.1"
    port = int(sys.argv[1])
    start_client(server_ip, port)
