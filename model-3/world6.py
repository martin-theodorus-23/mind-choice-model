# proper working single layered 6 neuron model

import pybullet as p
import pybullet_data
import time
import math
import random
import threading
import copy
import json
import os
import tkinter as tk

# Global for UI communication (3 Inputs, 4 Hidden, 9 Outputs)
ui_data = {"inputs": [0.0]*3, "hidden": [0.0]*6, "outputs": [0.0]*9}

# ================= 1. THE BRAIN =================
class DeepRobotBrain:
    def __init__(self):
        # 3 Inputs -> 6 Hidden -> 9 Outputs (8 wheels + 1 STOP)
        # Hidden Knobs: (3 inputs + 1 bias) * 6 hidden nodes = 24
        self.hidden_knobs = [random.uniform(-1.0, 1.0) for _ in range(24)] 
        # Action Knobs: (6 hidden + 1 bias) * 9 output nodes = 63
        self.action_knobs = [random.uniform(-1.0, 1.0) for _ in range(63)] 

    def make_tweaked_clone(self, strength):
        baby = DeepRobotBrain()
        for i in range(len(self.hidden_knobs)):
            baby.hidden_knobs[i] = self.hidden_knobs[i] + random.uniform(-strength, strength)
        for i in range(len(self.action_knobs)):
            baby.action_knobs[i] = self.action_knobs[i] + random.uniform(-strength, strength)
        return baby

    def decide_action(self, angle, distance, yaw):
        # Normalization
        norm_angle = angle / 3.14159
        norm_dist = distance / 20.0
        norm_yaw = yaw / 3.14159
        inputs = [norm_angle, norm_dist, norm_yaw]
        
        # Calculate 6 Hidden Thoughts
        hidden_thoughts = [0.0] * 6
        knob_idx = 0
        for h in range(6):
            score = (inputs[0] * self.hidden_knobs[knob_idx] + 
                     inputs[1] * self.hidden_knobs[knob_idx+1] + 
                     inputs[2] * self.hidden_knobs[knob_idx+2] + 
                     self.hidden_knobs[knob_idx+3]) # Bias
            knob_idx += 4
            hidden_thoughts[h] = math.tanh(score)

        # Calculate 9 Action Scores based on the 6 Hidden Thoughts
        action_scores = [0.0] * 9 
        knob_idx = 0
        for a in range(9):
            score = 0
            for h in range(6):
                score += hidden_thoughts[h] * self.action_knobs[knob_idx]
                knob_idx += 1
            score += self.action_knobs[knob_idx] # Bias
            knob_idx += 1
            action_scores[a] = score

        return action_scores, hidden_thoughts, inputs

    def save_to_file(self, filename="best_brain_v3.json"):
        data = {"hidden_knobs": self.hidden_knobs, "action_knobs": self.action_knobs}
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)

    def load_from_file(self, filename="best_brain_v3.json"):
        with open(filename, "r") as f:
            data = json.load(f)
            self.hidden_knobs = data["hidden_knobs"]
            self.action_knobs = data["action_knobs"]

# ================= 2. THE VISUALIZER =================
def brain_visualizer_thread():
    root = tk.Tk()
    root.title("Neural Network Activity")
    canvas = tk.Canvas(root, width=400, height=700, bg="#121212")
    canvas.pack()

    def update_ui():
        canvas.delete("all")
        layers = [
            {"count": 3,  "x": 50,  "data": ui_data["inputs"], "name": "Input"},
            {"count": 6,  "x": 200, "data": ui_data["hidden"], "name": "Hidden"},
            {"count": 9,  "x": 350, "data": ui_data["outputs"], "name": "Output"}
        ]
        for layer in layers:
            spacing = 680 / (layer["count"] + 1)
            for i in range(layer["count"]):
                y = (i + 1) * spacing
                val = layer["data"][i]
                
                # Special styling for the 9th output (STOP action)
                if layer["name"] == "Output" and i == 8:
                    is_braking = math.tanh(val) > 0.0
                    color = "#ff0000" if is_braking else "#333333" # Red if braking, dark grey if driving
                    canvas.create_oval(layer["x"]-12, y-12, layer["x"]+12, y+12, fill=color, outline="white")
                    canvas.create_text(layer["x"]-30, y, text="STOP", fill="white", font=("Arial", 8, "bold"))
                else:
                    brightness = min(255, int(abs(val) * 200) + 55)
                    color = f"#00{brightness:02x}00" if val > 0 else f"#{brightness:02x}0000"
                    canvas.create_oval(layer["x"]-8, y-8, layer["x"]+8, y+8, fill=color, outline="white")
                    
        root.after(50, update_ui)

    update_ui()
    root.mainloop()

# ================= 3. UNIVERSE BUILDER =================
def build_universe(client_id):
    p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=client_id)
    p.setGravity(0, 0, -9.8, physicsClientId=client_id)
    p.loadURDF("plane.urdf", physicsClientId=client_id)

    startPos = [0, 0, 0.5]
    robot = p.loadURDF("husky/husky.urdf", startPos, [0,0,0,1], physicsClientId=client_id)
    
    wheel_joints = []
    for i in range(p.getNumJoints(robot, physicsClientId=client_id)):
        if "wheel" in p.getJointInfo(robot, i, physicsClientId=client_id)[1].decode("utf-8"):
            wheel_joints.append(i)

    # DUCK FIX: Anchored (mass=0) so it doesn't slide away
    duck = p.loadURDF("duck_vhacd.urdf", [2, 2, 0.5], p.getQuaternionFromEuler([1.57, 0, 0]), globalScaling=5, physicsClientId=client_id)
    p.changeDynamics(duck, -1, mass=10, physicsClientId=client_id)

    return robot, duck, wheel_joints, startPos

# ================= 4. THE MIND (TRAINING) =================
best_global_brain = DeepRobotBrain()
brain_ready = False 

def the_mind_thread():
    global best_global_brain, brain_ready
    mind_client = p.connect(p.DIRECT)
    robot, duck, wheel_joints, startPos = build_universe(mind_client)
    
    num_robots = 20
    generation = 1
    target_dist = 2.0 # CURRICULUM: Start very close

    if os.path.exists("best_brain_v2.json"):
        veteran = DeepRobotBrain()
        veteran.load_from_file("best_brain_v2.json")
        population = [veteran] + [veteran.make_tweaked_clone(0.1) for _ in range(num_robots - 1)]
    else:
        population = [DeepRobotBrain() for _ in range(num_robots)]

    while True:
        best_score_this_gen = 9999
        best_brain_this_gen = population[0]
        current_strength = max(0.01, 0.5 * (0.995 ** generation))

        # FIXED: Define the challenge ONCE per generation!
        angle = random.uniform(0, 2*math.pi)
        d_x, d_y = math.cos(angle)*target_dist, math.sin(angle)*target_dist
        robot_start_yaw = random.uniform(-3, 3)

        for brain in population:
            # Now, every brain gets the exact same setup
            p.resetBasePositionAndOrientation(duck, [d_x, d_y, 0.5], [0,0,0,1], physicsClientId=mind_client)
            p.resetBasePositionAndOrientation(robot, startPos, p.getQuaternionFromEuler([0,0,robot_start_yaw]), physicsClientId=mind_client)
            
            closest = 9999
            for step in range(1200): # Hard limit to prevent infinite loops
                pos, ori = p.getBasePositionAndOrientation(robot, mind_client)
                dist = math.hypot(d_x - pos[0], d_y - pos[1])
                if dist < closest: closest = dist
                
                if dist < 0.8: break # SUCCESS!

                r_yaw = p.getEulerFromQuaternion(ori)[2]
                rel_angle = (math.atan2(d_y-pos[1], d_x-pos[0]) - r_yaw + math.pi) % (2*math.pi) - math.pi
                
                # Update decide_action to pass all 3 inputs!
                scores, _, _ = brain.decide_action(rel_angle, dist, r_yaw)
                
                # Apply STOP logic
                is_braking = math.tanh(scores[8]) > 0.0
                
                for i in range(4):
                    if is_braking:
                        target_vel = 0.0
                    else:
                        target_vel = math.tanh(scores[i*2]-scores[i*2+1])*20
                        
                    p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, 
                                            targetVelocity=target_vel, force=50, physicsClientId=mind_client)
                p.stepSimulation(mind_client)

            if closest < best_score_this_gen:
                best_score_this_gen = closest
                best_brain_this_gen = brain

        # Evolution Logic
        if best_score_this_gen < 0.9: # If best reached the doll
            target_dist = min(20.0, target_dist + 0.5) # Level up difficulty
            if target_dist > 4.0: brain_ready = True

        best_global_brain = copy.deepcopy(best_brain_this_gen)
        best_global_brain.save_to_file("best_brain_v2.json")
        
        print(f"[MIND] Gen {generation} | Best: {round(best_score_this_gen, 2)}m | Difficulty: {round(target_dist,1)}m")
        
        # Kill 19, Keep 1, Clone 19
        population = [best_brain_this_gen] + [best_brain_this_gen.make_tweaked_clone(current_strength) for _ in range(num_robots-1)]
        generation += 1

# ================= 5. THE BODY (GUI) =================
body_client = p.connect(p.GUI)
robot, duck, wheel_joints, startPos = build_universe(body_client)

threading.Thread(target=the_mind_thread, daemon=True).start()
threading.Thread(target=brain_visualizer_thread, daemon=True).start()

current_brain = copy.deepcopy(best_global_brain)
tag_count = 0
while True:
    pos, ori = p.getBasePositionAndOrientation(robot, body_client)
    duck_pos, _ = p.getBasePositionAndOrientation(duck, body_client)
    dx, dy = duck_pos[0]-pos[0], duck_pos[1]-pos[1]
    dist = math.hypot(dx, dy)
    
    if dist < 1.0:
        tag_count += 1
        print(f"[BODY] TARGET NEUTRALIZED! Total: {tag_count}")
        
        p.resetBasePositionAndOrientation(duck, 
                                          [random.uniform(-10,10), 
                                           random.uniform(-10,10), 
                                           0.5], 
                                          [0,0,0,1], 
                                          body_client)
        
        p.resetBasePositionAndOrientation(robot, 
                                          [0,0,0.5], 
                                          [0,0,0,1], 
                                          body_client)
        time.sleep(0.5)
        continue

    current_brain = copy.deepcopy(best_global_brain)

    r_yaw = p.getEulerFromQuaternion(ori)[2]
    rel_angle = (math.atan2(dy, dx) - r_yaw + math.pi) % (2*math.pi) - math.pi
    
    # Update decide_action to pass all 3 inputs!
    scores, hid, ins = current_brain.decide_action(rel_angle, dist, r_yaw)
    
    # Update Visualizer Data
    ui_data["inputs"], ui_data["hidden"], ui_data["outputs"] = ins, hid, scores

    # Apply STOP logic in the Visualizer too
    is_braking = math.tanh(scores[8]) > 0.0

    for i in range(4):
        if is_braking:
            target_vel = 0.0
        else:
            target_vel = math.tanh(scores[i*2]-scores[i*2+1])*20
            
        p.setJointMotorControl2(robot, wheel_joints[i], p.VELOCITY_CONTROL, 
                                targetVelocity=target_vel, force=50, physicsClientId=body_client)
    
    p.stepSimulation(body_client)
    time.sleep(0.01)
    
    # Camera follow
    cam_dx, cam_dy = pos[0]-duck_pos[0], pos[1]-duck_pos[1]
    p.resetDebugVisualizerCamera(4.0, math.degrees(math.atan2(cam_dy, cam_dx))-90, -15, duck_pos, body_client)
