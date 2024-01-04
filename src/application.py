import socket
import struct
import argparse
import sys
import time
import random
###################### Argsparse##############################
def parse_arguments():
    parser = argparse.ArgumentParser(description='Codes')
    group = parser.add_mutually_exclusive_group(required=True) # adds a group for server and client only choose one
    group.add_argument('-c', '--client', action='store_true', help='Client mode') # Choose client mode
    group.add_argument('-s', '--server', action='store_true', help='Server mode') # Choose server mode
    parser.add_argument('-I', '--server_ip', type=str, default='127.0.0.1', help='IP Server') # Choose server ip
    parser.add_argument('-p', '--server_port', type=int, default=8088,help='select port for server') # Choose server port
    parser.add_argument('-r','--reliable_method', type=str, choices=['gbn', 'stop_and_wait', 'SR'], help='Reliable method') # -r reliable method (gbn) (stop_and_wait) (SR)
    parser.add_argument('-t','--testcase',type=str, choices=['skip_ack', 'loss','skip_seq'], help='testcase') # -t testcase (skip_ack) (loss)
    parser.add_argument('-f','--file',type=str, help='file to transfer') # -f file to transfer
    return parser.parse_args()

########## HEADER ##################

# Create and extract packet
HEADER_LENGTH = 12 # Length of header
MAX_DATA_LENGTH = 1460 # Max data length
DRTP_HEADER_FORMAT = "!I I H H" # Header format
def create_packet(sequence_number, acknowledgment_number, flags=None, data=None, window=64): # Create packet function
    if flags is None: # if flags is none sets syn ack fin to default 0
        flags = {'SYN': 0, 'ACK': 0, 'FIN': 0}

    flags_value = (flags['SYN'] << 15) | (flags['ACK'] << 14) | (flags['FIN'] << 13) # Integers for flags
    data_length = len(data) if data else 0
    header = struct.pack(DRTP_HEADER_FORMAT, sequence_number, acknowledgment_number, flags_value, window) # packs seq number ack number flags value and window into dtrp header format
    packet = header + (data if data else b"") # Makes a packet with header and data
    return packet


def extract_packet(packet): # extracts the information from the packet
    if len(packet) < HEADER_LENGTH: # Error handling
        raise ValueError("Packet is too short to be a DRTP packet")
    seq_num, ack_num, flags_value, window = struct.unpack(DRTP_HEADER_FORMAT, packet[:HEADER_LENGTH]) # unpacks packet
    flags = {'SYN': (flags_value >> 15) & 0x1, 'ACK': (flags_value >> 14) & 0x1, 'FIN': (flags_value >> 13) & 0x1}
    data = packet[HEADER_LENGTH:]

    return seq_num, ack_num, flags, window, data



def gbn_client(args):
    server_address = (args.server_ip, args.server_port)
    window_size = 5
    sequence_number = 1
    buffer = {}  # Store packets that haven't been acknowledged yet
    timeout = 0.5  # Default timeout value of 500ms
    buffer_size = 1472;

    # Create a UDP socket and connect to server
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.connect(server_address)

    # Send SYN packet to initiate three-way handshake
    packet = create_packet(sequence_number, acknowledgment_number=0, flags={'SYN': 1, 'ACK': 0, 'FIN': 0}, data=None)
    client_socket.send(packet)
    print(f'Sent SYN packet with sequence number: {sequence_number}')

    # Wait for SYN-ACK packet from server
    while True:
        # Set a timeout for waiting for a response
        client_socket.settimeout(timeout)

        # Receive packet from server
        try:
            response_packet, address = client_socket.recvfrom(1472)
        except socket.timeout:
            print('Timeout waiting for SYN-ACK packet from server')
            continue

        # Extract fields from packet
        response_sequence_number, ack_num, response_flags, response_window, response_data = extract_packet(response_packet)

        # Check if packet is SYN-ACK
        if response_flags['SYN'] == 1 and response_flags['ACK'] == 1:
            print(f'Received SYN-ACK packet with sequence number: {response_sequence_number}')

            # Send ACK packet to complete three-way handshake
            sequence_number += 1
            ack_packet = create_packet(sequence_number, acknowledgment_number=response_sequence_number + 1,
                                        flags={'SYN': 0, 'ACK': 1, 'FIN': 0}, data=None)
            if args.testcase == "skip_ack":
                print(f'Skipping ACK packet with sequence number: {sequence_number}')
            else:
                client_socket.send(ack_packet)
                print(f'Sent ACK packet with sequence number: {sequence_number}')

            break


    # Send packets test case 3
    with open(args.file, 'rb') as f:
        while True:
            # Reading
            data = f.read(buffer_size)
            if not data:
                break  # End of file

            # Create a packet with the next sequence number and send it to the server
            # Check if the sequence number is the one to be skipped
            # Test case 3

            if args.testcase == sequence_number:
                print(f'Skipping packet with sequence number: {sequence_number}')
            else:
                packet = create_packet(sequence_number + 1, acknowledgment_number=0, flags={'ACK': 0, 'SYN': 0, 'FIN': 0},
                                   data=data)
                client_socket.sendto(packet, (args.server_ip, args.server_port))
                print(f'Sent packet with sequence number: {sequence_number + 1}')

    #
    packets = (data)

    # declare variables
    window_start = 1
    window_end = window_start + window_size - 1

    # Send packets in window
    for packet in packets:
        if sequence_number >= window_start and sequence_number <= window_end:
            buffer[sequence_number] = packet
            client_socket.send(packet)
            print(f'Sent packet with sequence number: {sequence_number}')
            sequence_number += 1

        if sequence_number > window_end:
            break

    # Wait for ACK packets from the server
    while True:
        # Set a timeout for waiting for a response
        client_socket.settimeout(timeout)

        # Receive packet from server
        try:
            response_packet, address = client_socket.recvfrom(1472)
        except socket.timeout:
            print('Timeout waiting for ACK packet from server')
            # Resend unacknowledged packets
            for seq_num in range(window_start, sequence_number):
                if seq_num not in buffer:
                    continue

                client_socket.send(buffer[seq_num])
                print(f'Resent packet with sequence number: {seq_num}')

            continue

        # Extract fields from packet
        response_sequence_number, ack_num, response_flags, response_window, response_data = extract_packet(response_packet)

        # Check if packet is ACK
        if response_flags['SYN'] == 0 and response_flags['ACK'] == 1:
            print(f'Received ACK packet with sequence number: {ack_num}')



    # Close socket
    client_socket.close()



def sr_client(args):
    # Create socket
    server_address = (args.server_ip, args.server_port)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.connect(server_address)

    # Fixing variables for  sequence and acknowledgment numbers
    sequence_number = random.randint(1, 2 ** 32 - 1)
    expected_ack = 0
    bytes_sent = 0
    window_size = 5

    # Fixing variables for tracking packets and ack
    packets = []
    acks = []

    # Fixing timeouts and buffer var
    timeout = 0.5
    receive_buffer = []
    buffer_size = 1472

    # Send SYN packet to  server
    syn_packet = create_packet(sequence_number, acknowledgment_number=expected_ack,
                               flags={'ACK': 0, 'SYN': 1, 'FIN': 0}, data=None)
    client_socket.sendto(syn_packet, (args.server_ip, args.server_port))
    print(f'Sent SYN packet with sequence number: {sequence_number}')

    # Wait for SYN-ACK from the server we sent to
    while True:
        # Timeout waiting for receiveing packet
        client_socket.settimeout(timeout)

        try:
            # Receiveving packet from the server we sent to
            packet, address = client_socket.recvfrom(buffer_size)
            sequence_number, ack_num, flags, window_size, data = extract_packet(packet)

            # If it is syn ack, go out of the loop
            if flags['SYN'] and flags['ACK']:
                break
        except socket.timeout:
            # If timeout is done, resend SYN packet.
            print('Timeout expired, resending SYN packet...')
            client_socket.sendto(syn_packet, (args.server_ip, args.server_port))

    # Sending ACK to server
    ack_packet = create_packet(sequence_number + 1, acknowledgment_number=ack_num + 1,
                               flags={'ACK': 1, 'SYN': 0, 'FIN': 0}, data=None)
    client_socket.sendto(ack_packet, (args.server_ip, args.server_port))
    print(f'Sent ACK packet with acknowledgment number: {ack_num + 1}')

    # Opening the file
    # Dividing the data
    with open(args.file, 'rb') as f:
        while True:
            # Reading
            data = f.read(buffer_size)
            if not data:
                break  # End of file

            # Create a packet with the next sequence number and send it to the server
            # Check if the sequence number is the one to be skipped
            # Test case 2 3

            if args.testcase == "skip_ack" and args.testcase == sequence_number:
                print(f'Skipping ACK for packet with sequence number: {sequence_number}')
            else:
                packet = create_packet(sequence_number + 1, acknowledgment_number=0, flags={'ACK': 0, 'SYN': 0, 'FIN': 0},
                                   data=data)
                packets.append(packet)
                client_socket.sendto(packet, (args.server_ip, args.server_port))
                print(f'Sent packet with sequence number: {sequence_number + 1}')

            # Update seq number
            # Update bytes sent
            sequence_number += len(data)
            bytes_sent += len(data)

            # The code is trying to wait for an acknowledgment from the server after sending a message.
            while True:
                # It sets a timeout for waiting for an acknowledgment, and if it doesn't receive any acknowledgment within that time, it returns False
                client_socket.settimeout(timeout)

                try:
                    # Send message to  server
                    client_socket.sendall(())

                    # Wait for the server recognize
                    data = client_socket.recv(1472).decode()

                    if data == "ACK":
                        # It then waits for an acknowledgment again and prints it when received.
                        return True  # To do test case skip ack, we need to change this do break instead of return true

                except socket.timeout:
                    # If it times out waiting for an acknowledgment, it prints an error message and retries sending the message.
                    return False

                except socket.error:
                    # If the connection was reset, it prints an error message and closes the client socket.
                    return False

    # SKIP ACK TEST CASE 2 reset
    client_socket.close()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.connect(server_address)

    while True:
        # Setting timeout
        client_socket.settimeout(timeout)

        try:
            # Getting message from the server
            message = client_socket.recv(buffer_size).decode()

            # Message is not empty, printing and removing out of loop
            if message:
                print(f"Acknowledgment received: {message}")
                break

        except socket.timeout:

            print("Timed out waiting for acknowledgment. Retrying...")
            continue

        except ConnectionResetError:
            # If connectiong get reset
            # print and Close the socket
            print("Connection was reset by the server.")
            client_socket.close()
            sys.exit()

        except Exception as e:
            # If any other exception occurs, print an error message and close the client socket
            print(f"An error occurred: {e}")
            client_socket.close()
            sys.exit()


def saw_client(args):
    # Establish a connection with the server
    server_address = (args.server_ip, args.server_port)
    sequence_number = 1
    expected_ack = 0
    bytes_sent = 0

    # Create a UDP socket and connect to the server
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.connect(server_address)

    # Send SYN packet to initiate three-way handshake
    packet = create_packet(sequence_number, acknowledgment_number=0, flags={'SYN': 1, 'ACK': 0, 'FIN': 0}, data=None)
    client_socket.send(packet)
    print(f'Sent SYN packet with sequence number: {sequence_number}')
    response_packet, address = client_socket.recvfrom(1472)
    response_sequence_number, ack_num, response_flags, response_window, response_data = extract_packet(response_packet)
    print(f'Received response with sequence number: {response_sequence_number}')

    if response_flags['SYN'] and response_flags['ACK']:
        # Send ACK packet to complete three-way handshake
        sequence_number += 1
        packet = create_packet(sequence_number, acknowledgment_number=0, flags={'SYN': 0, 'ACK': 1, 'FIN': 0}, data=None)
        client_socket.send(packet)
        print(f'Sent ACK packet with sequence number: {sequence_number+1}')

        # Start sending data packets
        with open(args.file, 'rb') as f:
            start_time = time.time()
            while True:
                data = f.read(1472)
                if not data:
                    break  # End of file reached

                # Send packet and wait for ACK
                while True:
                    print('SIZE = {}'.format(len(data)))
                    if args.testcase == 'skip_ack':
                        # Skip sending ACK
                        print('Skipping sending ACK')
                    else:
                        packet = create_packet(sequence_number, acknowledgment_number=0, flags={'SYN': 0, 'ACK': 1, 'FIN': 0}, data=None)
                        client_socket.send(packet)

                    bytes_sent += len(data)
                    end_time = time.time()
                    time_elapsed = end_time - start_time
                    print(time_elapsed)
                    print(bytes_sent)
                    throughput = bytes_sent / time_elapsed
                    print(f'Throughput: {throughput:.2f} bytes/s')
                    print(f'Sent packet with sequence number: {sequence_number + 1}')

                    if args.testcase == 'skip_seq':
                        # Skip incrementing sequence number and expected ACK
                        print('Skipping sequence number increment')
                    else:
                        sequence_number += 1
                        expected_ack += 1

                    if args.testcase != 'skip_ack':
                        client_socket.settimeout(0.5)
                        try:
                            response_packet, address = client_socket.recvfrom(1472)
                            response_sequence_number, ack_num, response_flags, response_window, response_data = extract_packet(
                                response_packet)
                            print(f'Received ACK packet with sequence number: {response_sequence_number}')
                            if response_flags['ACK'] and response_sequence_number == expected_ack:
                                expected_ack += 1
                                sequence_number += 1
                        except socket.timeout:
                            # Timeout expired, retransmit the packet
                            print(f'Timeout expired, resending packet with sequence number: {sequence_number}')
                            continue

                if bytes_sent == len(data):
                    print(bytes_sent)
                    # All data has been transmitted
                    break

                    # Send FIN packet to close the connection
                packet = create_packet(sequence_number, acknowledgment_number=0, flags={'SYN': 0, 'ACK': 0, 'FIN': 1},
                                       data=None)
                client_socket.send(packet)
                print(f'Sent FIN packet with sequence number: {sequence_number}')
                response_packet, address = client_socket.recvfrom(1472)
                response_sequence_number, ack_num, response_flags, response_window, response_data = extract_packet(
                    response_packet)
                print(f'Received response with sequence number: {response_sequence_number}')
                if response_flags['FIN'] and response_flags['ACK']:
                    # Send ACK packet to confirm FIN
                    sequence_number += 1
                    packet = create_packet(sequence_number, acknowledgment_number=3,
                                           flags={'SYN': 0, 'ACK': 1, 'FIN': 0}, data=None)
                    client_socket.send(packet)
                    print(f'Sent ACK packet with sequence number: {sequence_number}')

                # Close the socket
            client_socket.close()



def server(args):
    # Set up server address and socket
    server_address = (args.server_ip, args.server_port)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(server_address)
    print('Server started and listening')

    # Wait for SYN packet to initiate three-way handshake
    while True:
        syn_packet, client_address = server_socket.recvfrom(1472)
        sequence_number, ack_number, flags, window_size, data = extract_packet(syn_packet)
        if flags['SYN']:
            print(f'Received SYN packet with sequence number: {sequence_number}')
            # Send SYN-ACK packet to complete three-way handshake
            ack_number = sequence_number
            syn_ack_packet = create_packet(sequence_number + 1, acknowledgment_number=ack_number,
                                           flags={'SYN': 1, 'ACK': 1, 'FIN': 0}, data=None)
            server_socket.sendto(syn_ack_packet, client_address)
            print(f'Sent SYN-ACK packet with sequence number: {sequence_number}, ack number: {ack_number}')
            break

    # Wait for data packets and send ACK packets
    expected_sequence_number = 1
    file_data = b''
    while True:
        data_packet, client_address = server_socket.recvfrom(1472)
        sequence_number, ack_number, flags, window_size, data = extract_packet(data_packet)
        if flags['FIN']:
            print(f'Received FIN packet with sequence number: {sequence_number}')
            # Send FIN-ACK packet to complete four-way handshake
            server_sequence_number = expected_sequence_number
            ack_number = sequence_number + 1  # Next expected packet number
            fin_ack_packet = create_packet(server_sequence_number, acknowledgment_number=ack_number,
                                           flags={'SYN': 0, 'ACK': 1, 'FIN': 1}, data=None)
            server_socket.sendto(fin_ack_packet, client_address)
            print(f'Sent FIN-ACK packet with sequence number: {server_sequence_number}, ack number: {ack_number}')
            break

        if sequence_number == expected_sequence_number:
            # Accept the packet and append data to file_data
            print(f'Received data packet with sequence number: {sequence_number}')
            file_data += data
            expected_sequence_number += 1
        else:
            # Discard the packet and wait for retransmission
            print(f'Discarded out-of-order packet with sequence number: {sequence_number}')

        # Send an ACK packet with the next expected sequence number
        server_sequence_number = expected_sequence_number - 1
        ack_packet = create_packet(server_sequence_number, acknowledgment_number=ack_number,
                                   flags={'SYN': 0, 'ACK': 1, 'FIN': 0}, data=None)
        server_socket.sendto(ack_packet, client_address)
        print(f'Sent ACK packet with sequence number: {server_sequence_number}, ack number: {ack_number}')

    # Write received data to a file
    with open(args.file, 'wb') as f:
        f.write(file_data)
        print(f'Successfully saved file {args.file}')
        print(file_data)

    server_socket.close()


# Run server or client
if __name__ == '__main__':  # Checks if script is being executed as main program
    args = parse_arguments()  # Parses the arguments using the first function
    if args.server:  # If server is set
        server(args)
    else:
        if args.client:  # if client is set
            if args.reliable_method == 'gbn': # Starts gbn
                gbn_client(args)
            elif args.reliable_method == 'stop_and_wait': # starts stop and wait
                saw_client(args)
            elif args.reliable_method == 'SR': # starts sr client
                sr_client(args)






