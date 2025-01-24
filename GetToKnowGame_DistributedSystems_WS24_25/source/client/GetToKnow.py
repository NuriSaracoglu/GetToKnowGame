import sys
import os
import uuid
import ast
from time import sleep

# Add the parent directory to the Python path to import modules located there
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Middleware class for communication and the PlayersList class to manage players
from middleware.middleware import Middleware
from Player import PlayersList
import json

# Global dictionary to store states
states = {}

# The Statemachine class handles the game states and transitions
class Statemachine():
    UUID = str(uuid.uuid4())  # Generate a unique ID for the instance
    gameRoomPort = 61424      # Default port for the game room
    currentState = ''         # The current state of the state machine

    # Nested State class represents an individual state in the state machine
    class State:
        total_States = 0  # Counter for total states

        def __init__(self, name):
            self.name = name                  # State's name
            self.id = self.total_States      # Assign a unique ID to the state
            self.total_States += 1           # Increment the total states count
            states[name] = self              # Add the state to the global states dictionary

        def run(self):
            pass  # Placeholder for the state's logic

    # Class method to switch between states
    @classmethod
    def switchToState(cls, targetState):
        # Call the `exit` method of the current state, if it exists
        if "exit" in dir(states[cls.currentState]):
            states[cls.currentState].exit()

        # Call the `entry` method of the target state, if it exists
        if "entry" in dir(states[targetState]):
            states[targetState].entry()

        # Update the current state to the target state
        cls.currentState = targetState

    def __init__(self):
        # Initialize player management and other attributes
        self.players = PlayersList()  # Manage players
        self.question_answer = ""     # Stores the current question and answers
        self.commited_answers = 0     # Count of answers committed by players
        self.answered = False         # Flag to check if the player has answered
        Statemachine.UUID = str(uuid.uuid4())  # Assign a unique UUID to this instance
        self.middleware = Middleware(Statemachine.UUID, self)  # Initialize middleware for communication
        Statemachine.currentState = "Initializing"  # Set the initial state
        tempState = self.State("Initializing")  # Create the Initializing state

        # Define the logic for the Initializing state
        def state_initializing():
            print(f"UUID: {self.middleware.MY_UUID}")
            self.playerName = input("Select your Player Name: ")
            gamePort = input("Select Game Room Port (Leave Empty for default value of 61424) : ")
            self.gameRoomPort = (int(gamePort) if gamePort else 61424)
            self.players.addPlayer(self.middleware.MY_UUID, self.playerName)

            # Switch to the Lobby state
            self.switchToState("Lobby")
        tempState.run = state_initializing

        # Define the Lobby state
        tempState = self.State("Lobby")

        # Logic for when entering the Lobby state
        def Lobby_entry():
            self.middleware.leaderUUID = self.middleware.MY_UUID  # Set the player as the leader
            self.middleware.subscribeBroadcastListener(self.respondWithPlayerList)
            self.middleware.subscribeTCPUnicastListener(self.listenForPlayersList)
            command = "enterLobby"
            data = self.playerName
            print("\nSent Broadcast!")
            self.middleware.broadcastToAll(command, data)  # Notify all players
        tempState.entry = Lobby_entry

        # Logic for the Lobby state run method
        def lobby_waiting():
            sleep(0.5)  # Wait briefly before transitioning
            if self.middleware.leaderUUID == self.middleware.MY_UUID:
                self.switchToState("wait_for_peers")
            else:
                self.switchToState("wait_for_start")
        tempState.run = lobby_waiting

        # States specific to the leader of the quiz game
        tempState = self.State("wait_for_peers")

        # Logic for entering the wait_for_peers state
        def wait_for_peers_entry():
            if len(self.players.playerList) < 2:
                print("Waiting for more players - 2 players needed at minimum!")
        tempState.entry = wait_for_peers_entry

        # Logic for waiting for peers to join
        def wait_for_peers():
            if len(self.players.playerList) >= 2:
                self.players.printLobby()
                self.switchToState("start_new_round")
        tempState.run = wait_for_peers

        # Define the start_new_round state
        tempState = self.State("start_new_round")
        def start_new_round():
            # Collect questions and answers from the leader
            self.question = input("\n Here you can give your statements about yourself. Press enter to begin! \n")
            self.statement_1 = input("Statement 1: ")
            self.statement_2 = input("Statement 2: ")
            self.statement_3 = input("Statement 3: ")
            self.statement_4 = input("Statement 4: ")
            self.correct_answer = input("Enter the correct number (e.g., 1 or 2 or 3 or 4): ")
            self.question_answer = [self.question, self.statement_1, self.statement_2, self.statement_3, self.statement_4, self.correct_answer]
            
            # Broadcast the question to all players
            self.middleware.multicastReliable('startNewRound', str(self.question_answer))
            print(f'Multicasted question and answers: {str(self.question_answer)}')

            # Switch to waiting for responses
            self.switchToState("wait_for_responses")
        tempState.run = start_new_round

        # Additional states and their logic follow a similar pattern.
        # For brevity, this explanation focuses on core structures and transitions.
        
    # Logic to handle incoming player lists
    def listenForPlayersList(self, messengerUUID: str, messengerSocket, command: str, playersList: str):
        if command == 'PlayerList':
            self.middleware.leaderUUID = messengerUUID
            self.players.updateList(playersList)

    # Respond to a player's request to join the lobby
    def respondWithPlayerList(self, messengerUUID: str, command: str, playerName: str):
        if command == 'enterLobby':
            self.players.addPlayer(messengerUUID, playerName)
            if self.middleware.MY_UUID == self.middleware.leaderUUID:
                self.middleware.sendIPAdressesto(messengerUUID)
                responseCommand = 'PlayerList'
                responseData = self.players.toString()
                self.middleware.sendTcpMessageTo(messengerUUID, responseCommand, responseData)

    # Handle new round data received from the leader
    def onReceiveNewRound(self, messengerUUID, clientsocket, messageCommand, messageData):
        if messageCommand == "startNewRound":
            self.question_answer = ast.literal_eval(messageData)  # Parse the received data

    # Collect player responses
    def collectInput(self, messengerUUID, clientsocket, messageCommand, messageData):
        if messageCommand == 'playerResponse':
            self.commited_answers += 1
            if messageData == self.question_answer[-1]:
                self.players.addPoints(messengerUUID, 10)
            if self.middleware.leaderUUID == self.middleware.MY_UUID or self.answered:
                self.players.printLobby()

            if self.middleware.leaderUUID == self.middleware.MY_UUID and self.commited_answers == (len(self.players.playerList) - 1):
                self.switchToState("start_new_round")

    # Main loop for running the state machine
    def runLoop(self):
        states[self.currentState].run()

# Entry point for the program
if __name__ == '__main__':
    print("Welcome to the Get to Know Game!")
    SM = Statemachine()  # Initialize the state machine
    while True:
        SM.runLoop()  # Continuously run the state machine
