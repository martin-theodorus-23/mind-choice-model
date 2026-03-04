import pybullet as p
import pybullet_data
import time
import math
import random
import threading
import copy

# ================= 1. THE DEEP ROBOT BRAIN (With Hidden Layer) =================
class DeepRobotBrain:
    def __init__(self):
        # SENSES (2) -> HIDDEN THOUGHTS (5) -> ACTIONS (4)
        
        # Knobs connecting Senses to the Hidden Layer: (2 inputs * 5 neurons) + 5 biases = 15 knobs
        self.hidden_knobs = [random.uniform(-1.0, 1.0) for _ in range(15)]
        
        # Knobs connecting Hidden Layer to Actions: (5 neurons * 4 outputs) + 4 biases = 24 knobs
        self.action_knobs = [random.uniform(-1.0, 1.0) for _ in range(24)]

    def make_tweaked_clone(self):
        baby = DeepRobotBrain()
        
        # Clone and mutate hidden knobs (jiggle by up to 0.5)
        for i in range(15):
            baby.hidden_knobs[i] = self.hidden_knobs[i] + random.uniform(-0.5, 0.5)
            
        # Clone and mutate action knobs (jiggle by up to 0.5)
        for i in range(24):
            baby.action_knobs[i] = self.action_knobs[i] + random.uniform(-0.5, 0.5)
            
        return baby

    def decide_action(self, angle, distance):
        inputs = [angle, distance]
        hidden_thoughts = [0.0] * 5
        
        # --- STEP 1: Senses to Hidden Layer ---
        knob_idx = 0
        for h in range(5):
            score = 0
            for i in range(2):
                score += inputs[i] * self.hidden_knobs[knob_idx]
                knob_idx += 1
            # Add bias for this hidden neuron
            score += self.hidden_knobs[knob_idx]
            knob_idx += 1
            
            # THE SPARK! Squish the thought between -1 and 1
            hidden_thoughts[h] = math.tanh(score)

        # --- STEP 2: Hidden Layer to Actions ---
        action_scores = [0.0] * 4
        knob_idx = 0
        
        for a in range(4):
            score = 0
            for h in range(5):
                score += hidden_thoughts[h] * self.action_knobs[knob_idx]
                knob_idx += 1
            # Add bias for this action
            score += self.action_knobs[knob_idx]
            knob_idx += 1
            
            action_scores[a] = score

        # Return the index of the best action (0=Fwd, 1=Bwd, 2=Left, 3=Right)
        return action_scores.index(max(action_scores))

# ================= THE BRIDGE =================
best_global_brain = DeepRobotBrain()
brain_ready = False  # The Red/Green Light

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

# ================= 3. THREAD A: THE MIND (Invisible, Super Fast) =================
def the_mind_thread():
    global best_global_brain, brain_ready
    
    mind_client = p.connect(p.DIRECT)
    robot, duck, wheel_joints, startPos, startOri, aim = build_universe(mind_client)
    
    num_robots = 20
    steps_per_race = 1500 # Giving it plenty of time to drive 7 meters!
    population = [DeepRobotBrain() for _ in range(num_robots)]
    generation = 1

    while True:
        best_score = 999999
        best_brain_this_gen = None

        for brain in population:
            p.resetBasePositionAndOrientation(robot, startPos, startOri, physicsClientId=mind_client)
            
            for step in range(steps_per_race):
                pos, ori = p.getBasePositionAndOrientation(robot, physicsClientId=mind_client)
                duck_pos, _ = p.getBasePositionAndOrientation(duck, physicsClientId=mind_client)
                
                dx = duck_pos[0] - pos[0]
                dy = duck_pos[1] - pos[1]
                distance = math.hypot(dx, dy)
                
                robot_yaw = p.getEulerFromQuaternion(ori)[2]
                angle_to_duck = math.atan2(dy, dx)
                relative_angle = (angle_to_duck - robot_yaw + math.pi) % (2 * math.pi) - math.pi

                action_index = brain.decide_action(relative_angle, distance)

                if action_index == 0: speeds = [20, 20, 20, 20]
                elif action_index == 1: speeds = [-20, -20, -20, -20]
                elif action_index == 2: speeds = [-20, 20, -20, 20]
                elif action_index == 3: speeds = [20, -20, 20, -20]

                for i in range(4):
                    p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, targetVelocity=speeds[i], force=50, physicsClientId=mind_client)
                
                p.stepSimulation(physicsClientId=mind_client)

            pos, _ = p.getBasePositionAndOrientation(robot, physicsClientId=mind_client)
            final_dist = math.hypot(aim[0] - pos[0], aim[1] - pos[1])
            
            if final_dist < best_score:
                best_score = final_dist
                best_brain_this_gen = brain

        best_global_brain = copy.deepcopy(best_brain_this_gen)
        print(f"[MIND] Finished Gen {generation}. Best Distance: {round(best_score, 2)}m")

        # If it gets within 1 meter of the duck, it's ready!
        if best_score <= 1.0 and not brain_ready:
            print("\n[MIND] GOAL REACHED! The Deep Brain is trained. Waking up the Body!\n")
            brain_ready = True  

        next_gen = [best_brain_this_gen]
        for _ in range(num_robots - 1):
            next_gen.append(best_brain_this_gen.make_tweaked_clone())
            
        population = next_gen
        generation += 1

# ================= 4. THREAD B: THE BODY (Visible, Real-Time) =================
body_client = p.connect(p.GUI)
robot, duck, wheel_joints, startPos, startOri, aim = build_universe(body_client)

training_thread = threading.Thread(target=the_mind_thread, daemon=True)
training_thread.start()

print("[BODY] Simulation started. I am sitting in 'Park' while my Deep Mind trains...")
while not brain_ready:
    p.stepSimulation(physicsClientId=body_client)
    time.sleep(0.01)

print("[BODY] Upload complete! Let's go!")

# Infinite loop: Acting in the real world
while True:
    current_brain = copy.deepcopy(best_global_brain)
    
    pos, ori = p.getBasePositionAndOrientation(robot, physicsClientId=body_client)
    duck_pos, _ = p.getBasePositionAndOrientation(duck, physicsClientId=body_client)
    
    dx = duck_pos[0] - pos[0]
    dy = duck_pos[1] - pos[1]
    distance = math.hypot(dx, dy)
    
    robot_yaw = p.getEulerFromQuaternion(ori)[2]
    angle_to_duck = math.atan2(dy, dx)
    relative_angle = (angle_to_duck - robot_yaw + math.pi) % (2 * math.pi) - math.pi

    action_index = current_brain.decide_action(relative_angle, distance)

    if action_index == 0: speeds = [20, 20, 20, 20]
    elif action_index == 1: speeds = [-20, -20, -20, -20]
    elif action_index == 2: speeds = [-20, 20, -20, 20]
    elif action_index == 3: speeds = [20, -20, 20, -20]

    for i in range(4):
        p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, targetVelocity=speeds[i], force=50, physicsClientId=body_client)
    
    p.stepSimulation(physicsClientId=body_client)
    time.sleep(0.01) 
    
    p.resetDebugVisualizerCamera(cameraDistance=4.0, cameraYaw=robot_yaw*(180/math.pi), cameraPitch=-30, cameraTargetPosition=pos, physicsClientId=body_client)
    