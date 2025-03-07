import uuid
import threading
import socket
import logging
from time import sleep
from dataclasses import dataclass
from cluster import constants

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Middleware class handles communication between nodes in a distributed system
class Middleware():
    # Dictionary to store UUIDs and their corresponding IP addresses and ports
    ipAdresses = {}  # {uuid: (ip_address, port)} (str, int)
    MY_UUID = ''  # UUID of the current node
    neighborUUID = None  # UUID of the neighboring node
    neighborAlive = False  # Indicates if the neighboring node is alive

    def __init__(self, UUID, statemashine):
        Middleware.MY_UUID = UUID  # Assign current node's UUID
        self.statemashine = statemashine  # State machine for managing node state
        self._broadcastHandler = BroadcastHandler()  # Handles broadcasting messages
        self._unicastHandler = UDPUnicastHandler()  # Handles unicast communication over UDP
        self._tcpUnicastHandler = TCPUnicastHandler()  # Handles unicast communication over TCP

        # Subscribe to TCP Unicast listeners for various message handlers
        self.subscribeTCPUnicastListener(self._updateAdresses)
        self.subscribeTCPUnicastListener(self._checkForVotingAnnouncement)

        # Start a thread to send heartbeats periodically
        self.sendHB = threading.Thread(target=self._sendHeartbeats)
        self.sendHB.start()
        Middleware.neighborAlive = False
        self.subscribeUnicastListener(self._listenHeartbeats)
        self.subscribeTCPUnicastListener(self._listenLostPlayer)

        self.leaderUUID = ''  # UUID of the leader node

    # def findNeighbor(self, ownUUID, ipaddresses):
    #     """Find the nearest neighbor UUID in a sorted list of UUIDs."""
    #     ordered = sorted(ipaddresses.keys())
    #     if ownUUID in ordered:
    #         ownIndex = ordered.index(ownUUID)
    #         uuidList = list(ordered)
    #         if uuidList[ownIndex - 1] != ownUUID:
    #             return uuidList[ownIndex - 1]

    def _sendHeartbeats(self):
        """Periodically send heartbeat messages to the neighbor node to check its status."""
        ctr = 0
        while True:
            Middleware.neighborAlive = False
            if not Middleware.neighborUUID:
                # Find and assign a neighbor if not already assigned
                Middleware.neighborUUID = self.findNeighbor(Middleware.MY_UUID, Middleware.ipAdresses)
                sleep(1)
            else:
                # Send heartbeat ping to the neighbor
                self.sendMessageTo(Middleware.neighborUUID, 'hbping', Middleware.MY_UUID)
                sleep(1)
                if ctr < 3 and not Middleware.neighborAlive:
                    ctr += 1
                elif not Middleware.neighborAlive and ctr >= 3:
                    ctr = 0
                    Middleware.ipAdresses.pop(Middleware.neighborUUID, None)
                    self.statemashine.players.removePlayer(Middleware.neighborUUID)
                    self.multicastReliable('lostplayer', Middleware.neighborUUID)
                    if Middleware.neighborUUID == self.leaderUUID:
                        self.initiateLCRElection()  # New LCR election call
                    Middleware.neighborUUID = None
                elif Middleware.neighborAlive:
                    ctr = 0
                else:
                    Middleware.neighborUUID = None
                    ctr = 0

    def _listenHeartbeats(self, messengeruuid: str, command: str, data: str):
        """Handle incoming heartbeat messages."""
        if command == 'hbping':
            self.sendMessageTo(messengeruuid, 'hbresponse', Middleware.MY_UUID)
        elif command == 'hbresponse':
            if messengeruuid == Middleware.neighborUUID:
                Middleware.neighborAlive = True

    def _listenLostPlayer(self, messengerUUID: str, clientsocket: socket.socket, command: str, data: str):
        """Handle notification of a lost player."""
        if command == 'lostplayer':
            Middleware.ipAdresses.pop(data, None)
            Middleware.neighborUUID = None
            self.statemashine.players.removePlayer(data)

    @classmethod
    def addIpAdress(cls, uuid, addr):
        """Add a new IP address to the dictionary."""
        cls.ipAdresses[uuid] = addr
        Middleware.neighborUUID = None

    def broadcastToAll(self, command: str, data: str = ''):
        """Send a broadcast message to all nodes."""
        self._broadcastHandler.broadcast(command + ':' + data)

    def sendMessageTo(self, uuid: str, command: str, data: str = ''):
        """Send a unicast UDP message to a specific node."""
        ipAdress = Middleware.ipAdresses[uuid]
        self._unicastHandler.sendMessage(ipAdress, command + ':' + data)

    def sendTcpMessageTo(self, uuid: str, command: str, data: str = ''):
        """Send a unicast TCP message to a specific node."""
        addr = Middleware.ipAdresses[uuid]
        self._tcpUnicastHandler.sendMessage(addr, command + ':' + data)

    def sendTcpRequestTo(self, uuid: str, command: str, data: str = ''):
        """Send a TCP request to a specific node and wait for a response."""
        addr = Middleware.ipAdresses[uuid]
        return self._tcpUnicastHandler.sendTcpRequestTo(addr, command + ':' + data)

    def multicastReliable(self, command: str, data: str = ''):
        """Send a reliable multicast message to all nodes except the sender."""
        message = command + ':' + data
        for key, addr in Middleware.ipAdresses.items():
            if key != Middleware.MY_UUID:
                self._tcpUnicastHandler.sendMessage(addr, message)

    def sendIPAdressesto(self, uuid):
        """Send the IP address list to a specific node."""
        command = 'updateIpAdresses'
        s = self.leaderUUID + '$'
        for uuid, (addr, port) in Middleware.ipAdresses.items():
            s += uuid + ',' + str(addr) + ',' + str(port) + '#'
        self.sendTcpMessageTo(uuid, command, s)

    def subscribeBroadcastListener(self, observer_func):
        """Subscribe to receive broadcast messages."""
        self._broadcastHandler.subscribeBroadcastListener(observer_func)

    def subscribeUnicastListener(self, observer_func):
        """Subscribe to receive unicast messages."""
        self._unicastHandler.subscribeUnicastListener(observer_func)

    def subscribeTCPUnicastListener(self, observer_func):
        """Subscribe to receive TCP unicast messages."""
        self._tcpUnicastHandler.subscribeTCPUnicastListener(observer_func)

    def unSubscribeTCPUnicastListener(self, rmFunc):
        """Unsubscribe from TCP unicast messages."""
        self._tcpUnicastHandler.unSubscribeTCPUnicastListener(rmFunc)

    def _updateAdresses(self, messengerUUID: str, clientsocket, command: str, data: str):
        """Update the address list with received data."""
        if command == 'updateIpAdresses':
            data = data.split('$')
            self.leaderUUID = data[0]
            secondArgument = data[1]
            removedLastHashtag = secondArgument[0:-1]
            for addr in removedLastHashtag.split('#'):
                addrlist = addr.split(',')
                self.addIpAdress(addrlist[0], (addrlist[1], int(addrlist[2])))

    # def form_ring(self):
    #     """
    #     Forms a logical ring by sorting IP addresses of all known nodes.
    #     Returns the ordered list of IP addresses forming the ring.
    #     """
    #     try:
    #         # In your current structure, ipAdresses contains {uuid: (ip, port)}
    #         # We need to extract just the IPs for sorting
    #         ips = [addr[0] for uuid, addr in Middleware.ipAdresses.items()]
            
    #         # Convert to binary for proper IP sorting
    #         binary_ring = sorted([socket.inet_aton(ip) for ip in ips])
            
    #         # Convert back to string representation
    #         ip_ring = [socket.inet_ntoa(ip) for ip in binary_ring]
            
    #         print(f'Ring formed: {ip_ring}')
    #         return ip_ring
    #     except socket.error as e:
    #         print(f'Failed to form ring: {e}')
    #         return []

    # def getNextNodeInRing(self):
    #     """
    #     Determines the next node in the ring based on IP addresses.
    #     Returns the UUID of the next node.
    #     """
    #     # Form the ring of IP addresses
    #     ip_ring = self.form_ring()
    #     if not ip_ring:
    #         return Middleware.MY_UUID  # fallback for single-node situation
        
    #     # Find my IP in the ring
    #     my_ip = Middleware.ipAdresses[Middleware.MY_UUID][0]
        
    #     try:
    #         my_index = ip_ring.index(my_ip)
    #         next_index = (my_index + 1) % len(ip_ring)
    #         next_ip = ip_ring[next_index]
            
    #         # Find the UUID corresponding to this IP
    #         for uuid, addr in Middleware.ipAdresses.items():
    #             if addr[0] == next_ip:
    #                 return uuid
                    
    #         # If we couldn't find the UUID (shouldn't happen)
    #         return Middleware.MY_UUID
    #     except ValueError:
    #         # IP not found in ring (shouldn't happen)
    #         return Middleware.MY_UUID

    def form_ring(self):
        """
        Forms a logical ring by sorting UUIDs of all known nodes.
        Returns the ordered list of UUIDs forming the ring.
        """
        try:
            # Simply sort the UUIDs from the ipAddresses dictionary
            uuid_ring = sorted(Middleware.ipAdresses.keys())
            
            print(f'Ring formed (UUIDs): {uuid_ring}')
            return uuid_ring
        except Exception as e:
            print(f'Failed to form ring: {e}')
            return []

    def getNextNodeInRing(self):
        """
        Determines the next node in the ring based on UUIDs.
        Returns the UUID of the next node.
        """
        # Form the ring of UUIDs
        uuid_ring = self.form_ring()
        if not uuid_ring:
            return Middleware.MY_UUID  # fallback for single-node situation
        
        # Find my position in the ring
        try:
            my_index = uuid_ring.index(Middleware.MY_UUID)
            next_index = (my_index + 1) % len(uuid_ring)
            next_uuid = uuid_ring[next_index]
            
            # Make sure we're not returning our own UUID
            if next_uuid == Middleware.MY_UUID and len(uuid_ring) > 1:
                # If there are other nodes, find a different one
                for uuid in uuid_ring:
                    if uuid != Middleware.MY_UUID:
                        return uuid
                        
            return next_uuid
        except ValueError:
            # UUID not found in ring (shouldn't happen)
            print(f"Warning: Own UUID {Middleware.MY_UUID} not found in ring")
            if uuid_ring:
                return uuid_ring[0]  # Return first UUID if available
            return Middleware.MY_UUID

    def initiateLCRElection(self):
        """
        Initiates an LCR election by sending an 'lcr' message
        containing this node's own UUID to its ring successor.
        """
        command = 'lcr'
        data = Middleware.MY_UUID
        next_uuid = self.getNextNodeInRing()
        print(f"\nInitiating LCR election: sending {data} to {next_uuid}\n")
        self.sendTcpMessageTo(next_uuid, command, data)

    def _checkForVotingAnnouncement(self, messengerUUID: str, clientsocket: socket.socket, command: str, data: str):
        """
        Handles leader election messages using LCR.
        When a message with command 'lcr' is received, the node compares
        the election UID (data) with its own.
        """
        if command == 'lcr':
            # If the incoming UID equals our own, the message has traversed the ring.
            if data == Middleware.MY_UUID:
                print('\nI am the new Game-Master (Leader elected by LCR)!\n')
                self.leaderUUID = Middleware.MY_UUID
                self.statemashine.switchToState("start_new_round")
                self.multicastReliable('leaderElected', Middleware.MY_UUID)
            # If the incoming UID is lower than our own, override it with our UID and forward.
            elif data < Middleware.MY_UUID:
                new_data = Middleware.MY_UUID
                print(f'\nNode {Middleware.MY_UUID} replacing election UID {data} with my own, forwarding.')
                next_uuid = self.getNextNodeInRing()
                self.sendTcpMessageTo(next_uuid, 'lcr', new_data)
            # If the incoming UID is higher than our own, simply forward it.
            elif data > Middleware.MY_UUID:
                print(f'\nNode {Middleware.MY_UUID} forwarding election UID {data}.')
                next_uuid = self.getNextNodeInRing()
                self.sendTcpMessageTo(next_uuid, 'lcr', data)

        elif command == 'leaderElected':
            print('New Leader got elected via LCR\n')
            self.leaderUUID = data
            self.statemashine.switchToState("wait_for_start")
    
    # def form_ring(self):
    #     logger.debug('Forming ring with list of known peers')
    #     try:
    #         binary_ring_from_peers_list = sorted([socket.inet_aton(element) for element in self.middleware.ipAdresses])
    #         ip_ring = [socket.inet_ntoa(ip) for ip in binary_ring_from_peers_list]
    #         logger.info(f'Ring formed: {ip_ring}')

    #         return ip_ring
    #     except socket.error as e:
    #         logging.error(f'Failed to form ring: {e}')
    #         return []

    # def initiateVoting(self):
    #     """Start a leader election process."""
    #     command = 'voting'
    #     data = Middleware.MY_UUID
    #     self.sendTcpMessageTo(self.findLowerNeighbour(), command, data)

    # def findLowerNeighbour(self):
    #     """Find the UUID of the node's lower neighbor."""
    #     ordered = sorted(self.ipAdresses.keys())
    #     ownIndex = ordered.index(Middleware.MY_UUID)
    #     neighbourUUID = ordered[ownIndex - 1]
    #     assert Middleware.MY_UUID != neighbourUUID, 'I am my own neighbor, this should not happen'
    #     return neighbourUUID
       

class UDPUnicastHandler():
    _serverPort = 0 

    def __init__(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)                                                    
        self._server_socket.bind(('', 0))
        UDPUnicastHandler._serverPort = self._server_socket.getsockname()[1]
        self.incommingUnicastHistory = []
        self._listenerList = [] 
        self._listen_UDP_Unicast_Thread = threading.Thread(target=self._listenUnicast)
        self._listen_UDP_Unicast_Thread.start()

    
    def sendMessage(self, addr, message:str):
        self._server_socket.sendto(str.encode(Middleware.MY_UUID + '_'+constants.IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message), addr)


    def _listenUnicast(self):

        while True:
            try:
                data, address = self._server_socket.recvfrom(constants.BUFFER_SIZE)
                data = data.decode('utf-8')


                if data:
                    data=data.split('_')
                    messengerUUID = data[0]
                    messengerIP = data[1]
                    messengerPort = int(data[2])    
                                                    
                    assert address ==  (messengerIP, messengerPort)                              
                    message=data[3]
                    messageSplit= message.split(':')
                    assert len(messageSplit) == 2, "There should not be a ':' in the message"
                    messageCommand = messageSplit[0]
                    messageData = messageSplit[1]

                    self.incommingUnicastHistory.append((message, address))
                    for observer_func in self._listenerList:
                        observer_func(messengerUUID, messageCommand, messageData) 
                    data[1] = None
            except:
                pass

    def subscribeUnicastListener(self, observer_func):
        self._listenerList.append(observer_func)

class TCPUnicastHandler():
    def __init__(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', UDPUnicastHandler._serverPort))

        self.incommingUnicastHistory = []
        self._listenerList = []
        self._listen_UDP_Unicast_Thread = threading.Thread(target=self._listenTCPUnicast)
        self._listen_UDP_Unicast_Thread.start()

    
    def sendMessage(self, addr: tuple, message:str): 
        threading.Thread(target = self._sendMessageThread, args = (addr,message)).start()

    def _sendMessageThread(self, addr: tuple, message:str):
        sendSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sendSocket.bind(('', 0))

        try:
            sendSocket.connect(addr)
            messageBytes = str.encode(Middleware.MY_UUID + '_'+constants.IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message)
            sendSocket.send(messageBytes)
        except ConnectionRefusedError:
            pass
        finally:
            sendSocket.close()
        
        
    def sendTcpRequestTo(self, addr:tuple, message:str):
        sendSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sendSocket.bind(('', 0))
        response = None
        try:
            sendSocket.connect(addr)
            messageBytes = str.encode(Middleware.MY_UUID + '_'+constants.IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+message)
            sendSocket.send(messageBytes)
            response = sendSocket.recv(constants.BUFFER_SIZE).decode('utf-8')
        except ConnectionRefusedError:
            print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  ERROR')
            print('Process on address ', addr, 'is not connecting')
        finally:
            sendSocket.close()
        return response



    def _listenTCPUnicast(self):
        self._server_socket.listen(5)

        while True:
            clientsocket, address = self._server_socket.accept()
            clientsocket.settimeout(60)
            threading.Thread(target = self._listenToClient, args = (clientsocket,address)).start()


    def _listenToClient(self, clientsocket:socket.socket, address):
        data = clientsocket.recv(constants.BUFFER_SIZE)
        data = data.decode('utf-8')

        if data:
            data=data.split('_')
            messengerUUID = data[0]
            messengerIP = data[1]
            messengerPort = int(data[2])
                             
            message=data[3]
            messageSplit= message.split(':')
            assert len(messageSplit) == 2, "There should not be a ':' in the message"
            messageCommand = messageSplit[0]
            messageData = messageSplit[1]
            self.incommingUnicastHistory.append((message, address))
            for observer_func in self._listenerList:
                observer_func(messengerUUID, clientsocket, messageCommand, messageData)
        clientsocket.close()

    def subscribeTCPUnicastListener(self, observer_func):
        self._listenerList.append(observer_func)
        
    def unSubscribeTCPUnicastListener(self, rmFunc):
        self._listenerList = [x for x in self._listenerList if x != rmFunc]
        
class BroadcastHandler():
    def __init__(self):
        self.incommingBroadcastHistory = []
        self._listenerList = []
        self._broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listen_socket.bind((constants.IP_ADRESS_OF_THIS_PC, constants.BROADCAST_PORT))
        self._listen_UDP_Broadcast_Thread = threading.Thread(target=self._listenUdpBroadcast)
        self._listen_UDP_Broadcast_Thread.start()

    def broadcast(self, broadcast_message:str):
        """Send message to the broadcast Port defined at lauch of the Programm

        Args:
            broadcast_message (str): needs to have the format  "command:data" (the data could be csv encode with , and #)
        """
        self._broadcast_socket.sendto(str.encode(Middleware.MY_UUID + '_'+constants.IP_ADRESS_OF_THIS_PC + '_'+str(UDPUnicastHandler._serverPort)+'_'+broadcast_message, encoding='utf-8'), (constants.BROADCAST_IP, constants.BROADCAST_PORT))

    def subscribeBroadcastListener(self, observer_func):
        self._listenerList.append(observer_func)
    def _listenUdpBroadcast(self):
        while True:
            data, addr = self._listen_socket.recvfrom(constants.BUFFER_SIZE)
            data = data.decode('utf-8')
            if data:
                data=data.split('_')
                messengerUUID = data[0]
                messengerIP = data[1]
                messengerPort = int(data[2])
                message=data[3]
                Middleware.addIpAdress(messengerUUID,(messengerIP, messengerPort))
                if messengerUUID != Middleware.MY_UUID:
                    message=data[3]
                    messageSplit= message.split(':')
                    assert len(messageSplit) == 2, "There should not be a ':' in the message"
                    messageCommand = messageSplit[0]
                    messageData = messageSplit[1]
                    self.incommingBroadcastHistory.append((messengerUUID, message))
                    for observer_func in self._listenerList:
                        observer_func(messengerUUID, messageCommand, messageData)
                data = None