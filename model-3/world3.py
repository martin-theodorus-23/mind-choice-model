# Deep learning modal added to world

import pybullet as p
import pybullet_data
import time
import math
import random

# ================= THE ROBOT BRAIN =================
class RobotBrain:
    def __init__(self):
        # We need 12 knobs. 
        # (2 sensors: angle & distance, plus 1 baseline 'bias') x 4 actions = 12 knobs
        self.knobs = [random.uniform(-1.0, 1.0) for _ in range(12)]

    def make_tweaked_clone(self):
        baby = RobotBrain()
        for i in range(12):
            # Copy parent's knob, but jiggle it by up to 20%
            jiggle = random.uniform(-0.2, 0.2)
            baby.knobs[i] = self.knobs[i] + jiggle
        return baby

    def decide_action(self, angle, distance):
        # This is where the knobs do their work! 
        # They multiply the sensor numbers to give a "score" to each action.
        
        # 1. Score for driving FORWARD
        score_fwd = (angle * self.knobs[0]) + (distance * self.knobs[1]) + self.knobs[2]
        # 2. Score for driving BACKWARD
        score_bwd = (angle * self.knobs[3]) + (distance * self.knobs[4]) + self.knobs[5]
        # 3. Score for spinning LEFT
        score_left = (angle * self.knobs[6]) + (distance * self.knobs[7]) + self.knobs[8]
        # 4. Score for spinning RIGHT
        score_right = (angle * self.knobs[9]) + (distance * self.knobs[10]) + self.knobs[11]

        scores = [score_fwd, score_bwd, score_left, score_right]
        
        # Return the index of the action with the highest score (0, 1, 2, or 3)
        return scores.index(max(scores))


# ================= ENVIRONMENT SETUP =================
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)
plane = p.loadURDF("plane.urdf")

# Load Husky
startPos = [0, 0, 0.5]
startOrientation = p.getQuaternionFromEuler([0, 0, 0])
robot = p.loadURDF("husky/husky.urdf", startPos, startOrientation)

# Get Wheel Joints
num_joints = p.getNumJoints(robot)
wheel_joints = [i for i in range(num_joints) if "wheel" in p.getJointInfo(robot, i)[1].decode("utf-8")]

# Load Duck
aim = (5, 5, 0) # Put duck closer (5,5) so it learns faster!
duck_start_pos = [aim[0], aim[1], 0.5]
duck = p.loadURDF("duck_vhacd.urdf", duck_start_pos, p.getQuaternionFromEuler([1.57, 0, 0]), globalScaling=5)

# ================= THE EVOLUTION GAME =================
num_robots = 20  # How many robots per generation
steps_per_race = 150  # How many frames each robot gets to move
population = [RobotBrain() for _ in range(num_robots)]
generation = 1

while True:
    print(f"\n--- STARTING GENERATION {generation} ---")
    time.sleep(0.01)
    
    best_brain = None
    best_score = 999999  # Lowest distance wins

    # 1. TEST EVERY ROBOT IN THE POPULATION
    for brain_index, brain in enumerate(population):
        
        # Reset the robot to the starting line for this brain's turn
        p.resetBasePositionAndOrientation(robot, startPos, startOrientation)
        
        # Let this brain drive for a set number of steps
        for step in range(steps_per_race):
            
            # --- SENSE THE WORLD ---
            pos, ori = p.getBasePositionAndOrientation(robot)
            duck_pos, _ = p.getBasePositionAndOrientation(duck)
            
            # Calculate distance
            dx = duck_pos[0] - pos[0]
            dy = duck_pos[1] - pos[1]
            distance = math.hypot(dx, dy)
            
            # Calculate relative angle (Where is duck compared to where robot is looking?)
            robot_yaw = p.getEulerFromQuaternion(ori)[2]
            angle_to_duck = math.atan2(dy, dx)
            relative_angle = angle_to_duck - robot_yaw
            # Keep angle cleanly between -pi and pi
            relative_angle = (relative_angle + math.pi) % (2 * math.pi) - math.pi 

            # --- THINK ---
            action_index = brain.decide_action(relative_angle, distance)

            # --- ACT ---
            if action_index == 0:   # Forward
                speeds = [20, 20, 20, 20]
            elif action_index == 1: # Backward
                speeds = [-20, -20, -20, -20]
            elif action_index == 2: # Spin Left
                speeds = [-20, 20, -20, 20]
            elif action_index == 3: # Spin Right
                speeds = [20, -20, 20, -20]

            for i in range(4):
                p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, targetVelocity=speeds[i], force=50)
            
            p.stepSimulation()
            # Un-comment the next line if you want to watch it in slow-motion
            # time.sleep(0.01) 
            
            # Camera Follow
            p.resetDebugVisualizerCamera(cameraDistance=4.0, cameraYaw=robot_yaw*(180/math.pi), cameraPitch=-30, cameraTargetPosition=pos)

        # --- SCORE THIS ROBOT ---
        # The race is over. How close did it get?
        pos, _ = p.getBasePositionAndOrientation(robot)
        final_distance = math.hypot(aim[0] - pos[0], aim[1] - pos[1])
        
        if final_distance < best_score:
            best_score = final_distance
            best_brain = brain

    print(f"Gen {generation} Winner Distance: {round(best_score, 2)} meters")

    # 2. SURVIVAL OF THE FITTEST (Clone the winner)
    next_generation = []
    next_generation.append(best_brain) # Keep the exact winner so we don't go backwards
    
    for _ in range(num_robots - 1):
        # Create 19 slightly mutated babies of the winner
        next_generation.append(best_brain.make_tweaked_clone())
        
    population = next_generation
    generation += 1