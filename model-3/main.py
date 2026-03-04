# standred str for AI build space

import random as rm
import time


class World:
    def __init__(self):
        self.size = '200x500'
        self.ok = ''
    
    # here comes how world work and stimulations


class Agent:
    def __init__(self, name, world):
        self.name = name
        self.mind1 = {}
        self.mind2 = {}
        self.myWorld = world

    # Here comes what AI is doing

# Main loop that runs whole system
W = World()
A = Agent('A',W)
