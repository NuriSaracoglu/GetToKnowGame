from dataclasses import dataclass

@dataclass(order=True)
class Player():
    points:int
    uuid:str
    name:str

class PlayersList():
    def __init__(self):
        self.playerList = {} # {uuid: Player}
    
    def printLobby(self):
        print("Pointlist:".center(40,'_'))
        for player in sorted(self.playerList.values(), reverse=True):
            print('{:<30}'.format(player.name), " | ", player.points)
        
    
    def addPlayer(self, uuid:str, name:str, points:int = 0):
        self.playerList[uuid] = Player(points, uuid,name)

    def removePlayer(self, uuid: str):
        del self.playerList[uuid]

    
    def toString(self): # , , #
        s = ''
        for uuid, player in self.playerList.items():
            s += str(uuid)+','+str(player.name)+','+str(player.points)+'#'
        return s
    
    def addPoints(self, uuid:str, points:int):
        self.playerList[uuid].points += points

    def updateList(self, playersList:str):
        assert playersList[-1] =='#', f"the last character should be a #, maybe the string: {playersList} is empty"
        players = playersList.split('#')[0:-1]
        assert len(players) >= 2, "in this list there should be at least the sender and me"
        for player in players:
            player = player.split(',')
            uuid = player[0]
            name = player[1]
            points = int(player[2])
            self.addPlayer(uuid, name, points)
        self.printLobby()
