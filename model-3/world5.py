# saving my mind for next restart section

import pybullet as p
import pybullet_data
import time
import math
import random
import threading
import copy
import json  # <-- NEW: For saving/loading the brain
import os    # <-- NEW: For checking if the save file exists

# ================= 1. THE DEEP ROBOT BRAIN =================
class DeepRobotBrain:
    def __init__(self):
        # SENSES (5) -> HIDDEN THOUGHTS (16) -> ACTIONS (8)
        self.hidden_knobs = [random.uniform(-1.0, 1.0) for _ in range(96)]
        self.action_knobs = [random.uniform(-1.0, 1.0) for _ in range(136)]

    def make_tweaked_clone(self):
        baby = DeepRobotBrain()
        for i in range(96):
            baby.hidden_knobs[i] = self.hidden_knobs[i] + random.uniform(-0.5, 0.5)
        for i in range(136):
            baby.action_knobs[i] = self.action_knobs[i] + random.uniform(-0.5, 0.5)
        return baby

    def decide_action(self, rx, ry, ryaw, ax, ay):
        inputs = [rx, ry, ryaw, ax, ay] 
        hidden_thoughts = [0.0] * 16
        
        knob_idx = 0
        for h in range(16):
            score = 0
            for i in range(5):
                score += inputs[i] * self.hidden_knobs[knob_idx]
                knob_idx += 1
            score += self.hidden_knobs[knob_idx] 
            knob_idx += 1
            hidden_thoughts[h] = math.tanh(score)

        action_scores = [0.0] * 8
        knob_idx = 0
        for a in range(8):
            score = 0
            for h in range(16):
                score += hidden_thoughts[h] * self.action_knobs[knob_idx]
                knob_idx += 1
            score += self.action_knobs[knob_idx] 
            knob_idx += 1
            action_scores[a] = score

        return action_scores

    # --- NEW: SAVE AND LOAD FUNCTIONS ---
    def save_to_file(self, filename="best_brain.json"):
        data = {
            "hidden_knobs": self.hidden_knobs,
            "action_knobs": self.action_knobs
        }
        with open(filename, "w") as f:
            json.dump(data, f)

    def load_from_file(self, filename="best_brain.json"):
        with open(filename, "r") as f:
            data = json.load(f)
            self.hidden_knobs = data["hidden_knobs"]
            self.action_knobs = data["action_knobs"]

# ================= THE BRIDGE =================
best_global_brain = DeepRobotBrain()
brain_ready = False  

# ================= 2. UNIVERSE BUILDER =================
def build_universe(client_id):
    p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=client_id)
    p.setGravity(0, 0, -9.8, physicsClientId=client_id)
    p.loadURDF("plane.urdf", physicsClientId=client_id)

    startPos = [0, 0, 0.5]
    startOrientation = p.getQuaternionFromEuler([0, 0, 0])
    robot = p.loadURDF("husky/husky.urdf", startPos, startOrientation, physicsClientId=client_id)

    num_joints = p.getNumJoints(robot, physicsClientId=client_id)
    wheel_joints = []
    for i in range(num_joints):
        info = p.getJointInfo(robot, i, physicsClientId=client_id)
        if "wheel" in info[1].decode("utf-8"):
            wheel_joints.append(i)

    aim = (5, 5, 0)
    duck_pos = [aim[0], aim[1], 0.5]
    duck = p.loadURDF("duck_vhacd.urdf", duck_pos, p.getQuaternionFromEuler([1.57, 0, 0]), globalScaling=5, physicsClientId=client_id)

    return robot, duck, wheel_joints, startPos, startOrientation, aim

# ================= 3. THREAD A: THE MIND =================
def the_mind_thread():
    global best_global_brain, brain_ready
    
    mind_client = p.connect(p.DIRECT)
    robot, duck, wheel_joints, startPos, startOri, aim = build_universe(mind_client)
    
    num_robots = 20
    steps_per_race = 1500 
    population = []
    generation = 1

    # --- NEW: CHECK FOR SAVED BRAIN ON STARTUP ---
    if os.path.exists("best_brain.json"):
        print("\n[MIND] Found saved brain! Loading previous experience...")
        veteran_brain = DeepRobotBrain()
        veteran_brain.load_from_file("best_brain.json")
        population.append(veteran_brain) # Add the veteran
        for _ in range(num_robots - 1):
            population.append(veteran_brain.make_tweaked_clone()) # Make clones of the veteran
    else:
        print("\n[MIND] No saved brain found. Starting from scratch!")
        population = [DeepRobotBrain() for _ in range(num_robots)]

    while True:
        best_score = 999999
        best_brain_this_gen = None

        for brain in population:
            p.resetBasePositionAndOrientation(robot, startPos, startOri, physicsClientId=mind_client)
            
            for step in range(steps_per_race):
                pos, ori = p.getBasePositionAndOrientation(robot, physicsClientId=mind_client)
                duck_pos, _ = p.getBasePositionAndOrientation(duck, physicsClientId=mind_client)
                
                robot_yaw = p.getEulerFromQuaternion(ori)[2]

                scores = brain.decide_action(pos[0], pos[1], robot_yaw, duck_pos[0], duck_pos[1])

                speeds = [0, 0, 0, 0]
                speeds[0] = 20 if scores[0] > scores[1] else -20
                speeds[1] = 20 if scores[2] > scores[3] else -20
                speeds[2] = 20 if scores[4] > scores[5] else -20
                speeds[3] = 20 if scores[6] > scores[7] else -20

                for i in range(4):
                    p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, targetVelocity=speeds[i], force=50, physicsClientId=mind_client)
                
                p.stepSimulation(physicsClientId=mind_client)

            pos, _ = p.getBasePositionAndOrientation(robot, physicsClientId=mind_client)
            final_dist = math.hypot(aim[0] - pos[0], aim[1] - pos[1])
            
            if final_dist < best_score:
                best_score = final_dist
                best_brain_this_gen = brain

        # Share the best brain and SAVE IT to the hard drive
        best_global_brain = copy.deepcopy(best_brain_this_gen)
        best_global_brain.save_to_file("best_brain.json") # <-- NEW: Saving progress!
        
        print(f"[MIND] Gen {generation} | Best Dist: {round(best_score, 2)}m | Progress Saved.")

        if best_score <= 1.0 and not brain_ready:
            print("\n[MIND] GOAL REACHED! Complex Brain Trained. Waking up the Body!\n")
            brain_ready = True  

        next_gen = [best_brain_this_gen]
        for _ in range(num_robots - 1):
            next_gen.append(best_brain_this_gen.make_tweaked_clone())
            
        population = next_gen
        generation += 1

# ================= 4. THREAD B: THE BODY =================
body_client = p.connect(p.GUI)
robot, duck, wheel_joints, startPos, startOri, aim = build_universe(body_client)

training_thread = threading.Thread(target=the_mind_thread, daemon=True)
training_thread.start()

print("[BODY] Simulation started. Waiting for 232-knob brain to compile...")
while not brain_ready:
    p.stepSimulation(physicsClientId=body_client)
    time.sleep(0.01)

print("[BODY] Upload complete! I have raw senses. Let's go!")

while True:
    current_brain = copy.deepcopy(best_global_brain)
    
    pos, ori = p.getBasePositionAndOrientation(robot, physicsClientId=body_client)
    duck_pos, _ = p.getBasePositionAndOrientation(duck, physicsClientId=body_client)
    robot_yaw = p.getEulerFromQuaternion(ori)[2]

    scores = current_brain.decide_action(pos[0], pos[1], robot_yaw, duck_pos[0], duck_pos[1])

    speeds = [0, 0, 0, 0]
    speeds[0] = 20 if scores[0] > scores[1] else -20
    speeds[1] = 20 if scores[2] > scores[3] else -20
    speeds[2] = 20 if scores[4] > scores[5] else -20
    speeds[3] = 20 if scores[6] > scores[7] else -20

    for i in range(4):
        p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, targetVelocity=speeds[i], force=50, physicsClientId=body_client)
    
    p.stepSimulation(physicsClientId=body_client)
    time.sleep(0.01) 
    p.resetDebugVisualizerCamera(cameraDistance=4.0, cameraYaw=robot_yaw*(180/math.pi), cameraPitch=-30, cameraTargetPosition=pos, physicsClientId=body_client)

    if pos == duck_pos:
        break