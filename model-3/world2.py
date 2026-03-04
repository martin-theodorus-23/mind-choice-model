# proper world stimulation

import pybullet as p
import pybullet_data
import time
import random as rm

# ================= CONNECT TO GUI =================
physicsClient = p.connect(p.GUI)

# ================= ENVIRONMENT SETUP =================
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

plane = p.loadURDF("plane.urdf")

# ================= LOAD ROBOT =================
startPos = [0, 0, 0.5]
startOrientation = p.getQuaternionFromEuler([0, 0, 0])

robot = p.loadURDF("husky/husky.urdf", startPos, startOrientation)

# ================= GET JOINT INFO =================
num_joints = p.getNumJoints(robot)

print("\n==== JOINT INFO ====\n")
wheel_joints = []

for i in range(num_joints):
    info = p.getJointInfo(robot, i)
    joint_name = info[1].decode("utf-8")
    
    print("Joint", i, ":", joint_name)
    
    # Husky wheel joints contain the word "wheel"
    if "wheel" in joint_name:
        wheel_joints.append(i)

print("\nWheel joints:", wheel_joints)

# ================= DISABLE DEFAULT MOTOR =================
for j in wheel_joints:
    p.setJointMotorControl2(
        bodyUniqueId=robot,
        jointIndex=j,
        controlMode=p.VELOCITY_CONTROL,
        targetVelocity=0,
        force=0
    )

# ================= SET GOAL & LOAD DUCK =================
aim = (64, 30, 0)

# Load the built-in PyBullet duck at the aim location
# Setting Z slightly above 0 so it doesn't clip through the floor
duck_start_pos = [aim[0], aim[1], 0.5] 
duck_start_orientation = p.getQuaternionFromEuler([1.57, 0, 0]) # Rotate to stand upright

duck = p.loadURDF("duck_vhacd.urdf", duck_start_pos, duck_start_orientation, globalScaling=5)

# ================= SIMULATION LOOP =================
"""
Joint 1 : imu_joint
Joint 2 : front_left_wheel
Joint 3 : front_right_wheel
Joint 4 : rear_left_wheel
Joint 5 : rear_right_wheel
Joint 6 : top_plate
Joint 7 : user_rail
Joint 8 : front_bumper
Joint 9 : rear_bumper
"""

actions = [
    "motor1:forward", "motor1:backward", 
    "motor2:forward", "motor2:backward", 
    "motor3:forward", "motor3:backward",
    "motor4:forward", "motor4:backward",
    ]

mind = {
    "now$aim$distance": [1]*len(actions)  # Initialize weights for each action
}

moves = []
while True:

    position, orientation = p.getBasePositionAndOrientation(duck)
    aim = (position[0], position[1], 0)

    # --- NEW: CAMERA FOLLOW LOGIC ---
    # 1. Get the current position of the robot
    position, orientation = p.getBasePositionAndOrientation(robot)
    pos1 = position
    distance1 = abs(aim[0] - pos1[0]) + abs(aim[1] - pos1[1])

    # Convert all tuple numbers to strings and join them with an underscore
    p_str = "_".join([str(round(pos1[0])),str(round(pos1[1]))])
    a_str = "_".join([str(round(aim[0])),str(round(aim[1]))])

    sense = f"{p_str}${a_str}${round(distance1)}${moves[-10:]}"
    print(sense)

    # think 
    if sense not in mind:
        mind[sense] = [1]*len(actions)
    act = rm.choices(actions, weights=mind[sense], k=1)[0]

    moves.append(act)

    if act == "motor1:forward":
        dis = 20
        j = wheel_joints[0]
    elif act == "motor1:backward":
        dis = -20
        j = wheel_joints[0]
    elif act == "motor2:forward":
        dis = 20
        j = wheel_joints[1]
    elif act == "motor2:backward":
        dis = -20
        j = wheel_joints[1]
    elif act == "motor3:forward":
        dis = 20
        j = wheel_joints[2]
    elif act == "motor3:backward":
        dis = -20
        j = wheel_joints[2]
    elif act == "motor4:forward":
        dis = 20
        j = wheel_joints[3]
    elif act == "motor4:backward":
        dis = -20
        j = wheel_joints[3]
    else:
        dis = 0
        j = None

    p.setJointMotorControl2(
        bodyUniqueId=robot,
        jointIndex=j,
        controlMode=p.VELOCITY_CONTROL,
        targetVelocity=dis,   # speed
        force=50             # torque   
    )
    p.stepSimulation()
    time.sleep(0.01)

    position, orientation = p.getBasePositionAndOrientation(robot)
    pos2 = position
    distance2 = abs(aim[0] - pos2[0]) + abs(aim[1] - pos2[1])

    if pos2 == aim:
        print("Target Reached!")
        break

    # learn
    if distance1 > distance2:
        mind[sense][actions.index(act)] += 10

    elif distance1 == distance2:
        mind[sense][actions.index(act)] += 5
            
    elif distance1 < distance2:
        mind[sense][actions.index(act)] -= 10
        if mind[sense][actions.index(act)] < 1:
            mind[sense][actions.index(act)] = 1
    
    # camera follow
    p.resetDebugVisualizerCamera(
        cameraDistance=3.0,     # How far away the camera is
        cameraYaw=orientation[0],           # Left/right angle
        cameraPitch=-30,        # Up/down angle
        cameraTargetPosition=position  # Target the robot's [X, Y, Z]
    )
    