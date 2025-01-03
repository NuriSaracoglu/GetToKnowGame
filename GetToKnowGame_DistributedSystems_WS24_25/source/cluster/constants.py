import socket
import ipaddress

BROADCAST_PORT = 61424
BUFFER_SIZE = 1024
SUBNETMASK = "255.255.255.0"

IP_ADRESS_OF_THIS_PC = socket.gethostbyname(socket.gethostname())
net = ipaddress.IPv4Network(IP_ADRESS_OF_THIS_PC + '/' + SUBNETMASK, False)
BROADCAST_IP = net.broadcast_address.exploded