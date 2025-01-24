from dataclasses import dataclass

# Define a Player class to represent individual players, using the @dataclass decorator
# The `order=True` parameter allows comparison of Player objects based on their fields in the defined order.
@dataclass(order=True)
class Player():
    points: int  # Player's points (used for sorting as it's the first field)
    uuid: str    # Unique identifier for the player
    name: str    # Player's name

# Define a class to manage a list of players and their operations.
class PlayersList():
    def __init__(self):
        # Dictionary to store players with their UUID as the key
        self.playerList = {} # {uuid: Player}
    
    # Print the lobby of players sorted by their points (highest first)
    def printLobby(self):
        print("Pointlist:".center(40, '_'))  # Print a centered title with underscores
        # Sort players by points in descending order (reverse=True) and print their details
        for player in sorted(self.playerList.values(), reverse=True):
            print('{:<30}'.format(player.name), " | ", player.points)
    
    # Add a player to the player list
    def addPlayer(self, uuid: str, name: str, points: int = 0):
        # Create a new Player object and store it in the dictionary
        self.playerList[uuid] = Player(points, uuid, name)

    # Remove a player from the player list based on their UUID
    def removePlayer(self, uuid: str):
        # Delete the player object from the dictionary
        del self.playerList[uuid]

    # Convert the player list to a string representation
    def toString(self): 
        s = ''  # Initialize an empty string
        # Iterate over all players in the dictionary
        for uuid, player in self.playerList.items():
            # Append the player's details in the format "uuid,name,points#" to the string
            s += str(uuid) + ',' + str(player.name) + ',' + str(player.points) + '#'
        return s
    
    # Add points to a specific player
    def addPoints(self, uuid: str, points: int):
        # Increment the player's points by the given value
        self.playerList[uuid].points += points

    # Update the player list based on a string representation of players
    def updateList(self, playersList: str):
        # Ensure the string ends with '#' as a delimiter
        assert playersList[-1] == '#', f"the last character should be a #, maybe the string: {playersList} is empty"
        
        # Split the string by '#' to extract individual players, excluding the last empty part
        players = playersList.split('#')[0:-1]
        
        # Ensure the list contains at least two players (the sender and the current player)
        assert len(players) >= 2, "in this list there should be at least the sender and me"
        
        # Iterate over the player representations
        for player in players:
            # Split the player string into components: uuid, name, and points
            player = player.split(',')
            uuid = player[0]
            name = player[1]
            points = int(player[2])  # Convert points to an integer
            # Add the player to the player list
            self.addPlayer(uuid, name, points)
        
        # Print the updated lobby
        self.printLobby()
