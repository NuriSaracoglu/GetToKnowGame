import socket
import ipaddress

# Constants used in the program
BROADCAST_PORT = 61424  # The port number used for broadcasting messages
BUFFER_SIZE = 1024      # The buffer size for receiving data
SUBNETMASK = "255.255.255.0"  # Subnet mask used to calculate the broadcast IP address

# Get the IP address of the current machine
IP_ADRESS_OF_THIS_PC = socket.gethostbyname(socket.gethostname())

# Create an IPv4 network object using the current machine's IP and the subnet mask
net = ipaddress.IPv4Network(IP_ADRESS_OF_THIS_PC + '/' + SUBNETMASK, False)

# Calculate the broadcast IP address from the network object
BROADCAST_IP = net.broadcast_address.exploded  # Get the broadcast IP address as a string
