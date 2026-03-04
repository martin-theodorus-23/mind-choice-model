import tkinter as tk
import time
import random as rm

class RLGridWorld:
    def __init__(self, grid_size=20, cell_size=25):
        """
        Initializes the 2D grid world.
        :param grid_size: Number of cells per row/column.
        :param cell_size: Pixel size of each cell.
        """
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.width = self.grid_size * self.cell_size
        self.height = self.grid_size * self.cell_size
        
        # Tkinter GUI setup
        self.root = tk.Tk()
        self.root.title("2D RL Environment")
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg='white')
        self.canvas.pack()
        
        self._build_world()
        
    def _build_world(self):
        """Draws the grid lines and fruits."""
        # Draw grid lines
        for i in range(1, self.grid_size):
            self.canvas.create_line(i * self.cell_size, 0, i * self.cell_size, self.height, fill='lightgray')
            self.canvas.create_line(0, i * self.cell_size, self.width, i * self.cell_size, fill='lightgray')

        # Fruits in world
        self.fruits = []
        padding = max(1, self.cell_size // 5) # Proportional padding
        for _ in range(10):
            x = rm.randint(0, self.grid_size - 1)
            y = rm.randint(0, self.grid_size - 1)
            self.canvas.create_oval(
                x * self.cell_size + padding, y * self.cell_size + padding,
                x * self.cell_size + self.cell_size - padding, y * self.cell_size + self.cell_size - padding,
                fill='green'
            )

    def step(self, agent, action):
        """
        Executes the agent's action and updates the world.
        Actions: 0: Up, 1: Down, 2: Left, 3: Right
        """
        old_x, old_y = agent.agent_pos
        
        # 1. Apply action logic (with boundary checks)
        if action == 0 and agent.agent_pos[1] > 0:                    # Up
            agent.agent_pos[1] -= 1
        elif action == 1 and agent.agent_pos[1] < self.grid_size - 1: # Down
            agent.agent_pos[1] += 1
        elif action == 2 and agent.agent_pos[0] > 0:                    # Left
            agent.agent_pos[0] -= 1
        elif action == 3 and agent.agent_pos[0] < self.grid_size - 1: # Right
            agent.agent_pos[0] += 1
            
        # 2. Update the GUI for this specific agent
        dx = (agent.agent_pos[0] - old_x) * self.cell_size
        dy = (agent.agent_pos[1] - old_y) * self.cell_size
        self.canvas.move(agent.agent_gui, dx, dy)
        
        # 3. Formulate RL returns
        next_state = agent.agent_pos.copy()
        reward = -1    
        done = False   
        info = {}
        
        return next_state, reward, done, info
    
    def set_aim(self, aim, tag=''):
        """Highlights the target cell on the GUI."""
        self.canvas.delete(tag)  # Remove previous aim for this specific agent
        origin_x = aim[0] * self.cell_size
        origin_y = aim[1] * self.cell_size
        padding = max(1, self.cell_size // 5)
        
        self.canvas.create_rectangle(
            origin_x + padding, origin_y + padding,
            origin_x + self.cell_size - padding, origin_y + self.cell_size - padding,
            outline='red', width=2, tags=tag # Changed to outline so we can see the bot inside it
        )

    def draw_agent(self, position, color='blue'):
        """Draws the agent and returns its GUI ID."""
        origin_x = position[0] * self.cell_size
        origin_y = position[1] * self.cell_size
        padding = max(1, self.cell_size // 8)
        
        gui_id = self.canvas.create_rectangle(
            origin_x + padding, origin_y + padding,
            origin_x + self.cell_size - padding, origin_y + self.cell_size - padding,
            fill=color
        )
        return gui_id

    def render(self):
        """Forces Tkinter to update the screen."""
        self.root.update()


class Agent:
    def __init__(self, name, world):
        self.name = name
        self.world = world
        
        self.orgin = [0, 0]  # Starting position
        self.agent_pos = self.orgin.copy()  # Bot's personal position
        color = rm.choice(['blue', 'yellow', 'orange', 'purple', 'cyan'])

        # Draw the body and save the unique GUI ID
        self.agent_gui = self.world.draw_agent(self.agent_pos, color=color)

    def call(self):
        aim = self.select_aim()  
        self.world.set_aim(aim, tag=f"aim_{self.name}")  
        self.move_to_aim(aim)

    def select_aim(self):
        # Pick a random coordinate
        x = rm.randint(0, self.world.grid_size - 1)
        y = rm.randint(0, self.world.grid_size - 1)
        return [x, y]

    def move_to_aim(self, aim):
        weg = [1] * 4
        actions = [0, 1, 2, 3]

        while True:
            self.now = self.agent_pos.copy()
            
            # Check if we are already at the aim
            if aim == self.now:
                break
                
            distance1 = abs(aim[0] - self.now[0]) + abs(aim[1] - self.now[1])
            
            # Choose and take action
            think = rm.choices(actions, weights=weg, k=max(1, distance1)) # Prevent k=0 error
            action = max(set(think), key=think.count)
            
            # Pass THIS agent to the step function
            feed = self.world.step(self, action)

            self.world.render()  
            time.sleep(0.005) # Sped up slightly so 10 bots don't take forever

            new_pos = self.agent_pos 
            distance2 = abs(aim[0] - new_pos[0]) + abs(aim[1] - new_pos[1])

            # Update weights
            if distance1 > distance2:
                weg = [1] * 4
                weg[actions.index(action)] = 10
            elif distance1 == distance2:
                weg[actions.index(action)] = 1
            elif distance1 < distance2:
                weg = [1] * 4
                weg[actions.index(action)] = 1


if __name__ == "__main__":
    
    # Initialize the world (Adjusted size so it fits on screen nicely)
    env = RLGridWorld(grid_size=20, cell_size=30)
    env.render()

    bots = []
    for i in range(10):
        bot = Agent(f"Bot{i}", env)
        bots.append(bot)
    
    time.sleep(1) 
    
    try:
        while True:
            for bot in bots:
                env.root.title(f"2D RL Environment - {bot.name} is thinking...")
                bot.call()  
            
    except tk.TclError:
        # This prevents a massive error log if you close the window manually during the while loop
        print("Simulation closed.")