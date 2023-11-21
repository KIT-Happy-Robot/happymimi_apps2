#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
import math
import matplotlib.pyplot as plot
import os
import sys
from std_msgs.msg import Bool
from sensor_msgs import LaserScan
from geometry_msgs.msg import Twist

from find_bag.srv import Findbagsrv,FindBagSrvResponse,GraspBagSrv,GraspBagSrvResponse
from happymimi_msgs.srv import StrTrg
from happymimi_manipulation_msgs.srv import ArmControl

teleop_path = rclpy.packages.get_pkg_dir('happymimi_teleop')
sys.path.insert(os.path.join(teleop_path,'src/'),0)
from base_control import BaseControl

class FindBag():
    def __init__(self):
        super().__init__('find_bag')
        rclpy.Service('/find_bag_server',srv_FindBag,FindBagSrv)
        rclpy.loginfo('Ready to set /find_bag_server')
        rclpy.Service(srv_GraspBag,GraspBagSrv, '/grasp_bag_server')
        rclpy.loginfo("Ready to set /grasp_bag_server")
        #subscriber
        rclpy.Subscriber(laserCB,'/scan',Laserscan)
        rclpy.Subscriber(velCB,'/cmd_vel',Twist)
        #Mainpulation
        self.eef = rclpy.Publisher(Bool,'/servo/endeffector',queue_size=10,)
        self.arm_pose = rclpy.ServiceProxy(StrTrg,)
        self.manipulation = rclpy.ServiceProxy(ArmControl,'/servo/debug_arm')
        #Module
        self.base_control = BaseControl()
        #Value
        self.laser_list = []
        self.index_sum = []
        self.center_index = 0.0
        self.step_angle = 0.0
        self.rotate_value = 0.0
        self.bag_center = 0.0

    def laserCB(self,receive_msg):
        self.laser_list = list(receive_msg.ranges)

    def velCB(self,receive_msg):
        self.rotate_value = receive_msg.angular.z

    def laserCheck(self):
        while not self.laser_list and not rclpy.is_shutdown():
            rclpy.loginfo("NO laser data ...")
            rclpy.sleep(0.5)
        rclpy.loginfo("Laser data is available !")

    def startUp(self):
        self.laserCheck()
        self.index_sum = len(self.laser_list)
        self.step_angle = 180 / self.index_sum
        self.center_index = self.roundHalfUp(self.index_sum/2 - 1)
        print(f"\nNumber of laser data >>> {self.index_sum}")
        print(f"Degree per step >>> {self.step_angle}")
        print(f"Center of laser index >>> {self.center_index}\n")

    def roundHalfUp(self,value):
        decimals = math.modf(value)[0]
        return int(value + 1) if decimals >= 0.5 else int(value)

    def degToIndex(self,deg):
        return int(deg / self.step_angle)

    def average(self,input_list):
        ave = sum(input_list)/len(input_list)
        return ave

    def rangeDecrease(self,sensing_degree):
        laser_data = []
        laser_data = self.laser_list
        laser_range = self.degToIndex(sensing_degree)
        delete_range = int((self.index_sum - laser_range) / 2)
        if delete_range == 0:
            pass
        else:
            del laser_data[0 : delete_range + 1]
            del laser_data[laser_range + 1 :]
        return laser_data

    def bagRangeFind(self,left_right,sensing_degree):
        dispersion_param = 0.005
        laser_average = 'NULL'
        laser_deviation = 0
        laser_dispersion = 0
        spred_index = 0
        data_list = []
        bag_range = []
        range_dict = []
        #範囲を縮小
        laser_data = self.rangeDecrease(sensing_degree)
        self.laserIndex(laser_data)
        # データを左右に分割
        if left_right == 'left':
            search_range = laser_data[: self.center_index + 1]
        elif left_right =='right':
            search_range = laser_data[self.center_index :]
        else:
            search_range = laser_data #分割しない
        #データの最小値を見つける
        min_index = search_range.index(min(search_range))
        #バッグの検出(最小値から右)
        spread_index = min_index
        for data in search_range[min_index :]:
            data_list.append(data)
            laser_average = self.average(data)
            laser_deviation += (data - laser_average)**2
            laser_dispersion = laser_deviation/len(data_list)
            #print(laser_dispersion)
            if laser_dispersion < dispersion_param:
                bag_range.append(spread_index)
            elif laser_average != 'NULL' and laser_dispersion >= dispersion_param:
                print(f"========= {left_right.upper()} HALF ==========\n")
                print(f"Index of min data >>> {min_index}\n")
                print(bag_range)
                laser_deviation = 0
                data_list.clear()
                break
            else:
                pass
            spread_index += 1
            rclpy.sleep(0.05)
        # バッグの検出(最小値から左)
        search_range.reverse()
        spread_index = min_index - 1
        for data in search_range[search_range.index(min(search_range)) + 1:]:
            data_list.append(data)
            laser_average = self.average(data_list)
            laser_deviation += (data - laser_average(data_list))
            laser_dispersion = laser_deviation/len(data_list)
            #print(laser_dispersion)
            if laser_dispersion < dispersion_param:
                bag_range.insert(0,spread_index)
            elif laser_average != 'NULL' and laser_dispersion >= dispersion_param:
                print(f"\n=========={left_right.upper()}ALL ==============\n")
                print(bag_range)
                print()
                break
            else:
                pass
            spread_index -= 1
            rclpy.sleep(0.05)
        range_dict[left_right+ '_data'] = list(reversed(search_range))
        range_dict[left_right + '_bag_range'] = bag_range
        return range_dict
    
def rangeToAngle(self,left_right,range_dict):
    if left_right == 'left':
        self.bag_center = range_dict['left_bag_range'][self.roundHalfUp(len(range_dict['left_bag_range'])/2-1)]
        angle_to_bag = (len(range_dict['left_data'])- 1) - self.bag_center
   
    elif left_right == 'right':
        self.bag_center = range_dict['right_bag_range'][self.roundHalfUp(len(range_dict)['right_bag_range'])/2 - 1]
        angle_to_bag = -1*self.bag_center
    
    elif left_right == 'all':
        self.bag_center = range_dict['all_bag_range'][self.roundHalfUp(len(range_dict['all_bag_range'])/2 - 1)]
        angle_to_bag = self.center_index - self.bag_center
        print(f"Center Index: {self.center_index} >>> Bag Center: {self.bag_center}")
    else:
        pass
        return angle_to_bag*self.step_angle

    def bagFocus(self, left_right, sensing_degree=180, rotate_speed=0.7):
        if left_right == 'left' or left_right == 'right' or left_right == 'all':
            range_dict = self.bagRangeFind(left_right, sensing_degree)
        else:
            rclpy.loginfo("You are not typing correctly.")
        move_angle = self.rangeToAngle(left_right, range_dict)
        print(f'\nAngle to bag >>> {move_angle}\n')
        self.base_control.rotateAngle(move_angle, 1,  rotate_speed, 20)  # 回転の調整はここ
        while self.rotate_value != 0.0 and not rclpy.is_shutdown():
            rclpy.loginfo('Rotating ...')
            rclpy.sleep(0.5)
        rclpy.sleep(0.5)
        self.startUp()
        return self.laser_list[self.center_index]

    def bagGrasp(self, left_right, coordinate=[0.25, 0.4]):
        move_angle = 6
        if left_right == 'left':
            move_angle = -move_angle
        else:
            pass
        self.arm_pose('carry')
        self.eef.publish(False)
        dist_to_bag = self.bagFocus(left_right, 100, 0.7)
        print(coordinate)
        self.manipulation(coordinate)
        rclpy.sleep(1.0)
        self.base_control.translateDist(dist_to_bag - 0.30)
        rclpy.sleep(1.0)
        #self.scanPlot('all', 180)
        dist_to_bag = self.bagFocus('all', 100)
        # バッグの取っ手に指を通すために少し回転
        self.base_control.rotateAngle(move_angle, 1, 0.7, 20)
        rclpy.sleep(0.5)
        self.base_control.translateDist(dist_to_bag - 0.05, 0.1)
        rclpy.sleep(0.5)
        self.eef.publish(True)
        rclpy.sleep(0.5)
        self.arm_pose('carry')
        rclpy.loginfo('I have a bag.')

    def srv_FindBag(self, srv_req):
        distance = self.bagFocus(srv_req.left_right, srv_req.rotate_speed)
        return FindBagSrvResponse(result = True, distance = distance)

    def srv_GraspBag(self, srv_req):
        self.bagGrasp(srv_req.left_right, srv_req.data)
        return GraspBagSrvResponse(result = True)

    def scanPlot(self, left_right='NULL', sensing_degree=180):
        index = 0
        plot_data = {}
        scan_index_list = []
        rclpy.sleep(0.5)
        if left_right == 'left' or left_right == 'right' or left_right == 'all':
            plot_data = self.bagRangeFind(left_right, sensing_degree)
        else:
            rclpy.loginfo("You are not typing correctly.")
        self.rangeToAngle(left_right, plot_data)
        for data in plot_data[left_right + '_data']:
            scan_index_list.append(index)
            index += 1
        rclpy.loginfo("Plotting laser data.")
        plot.plot(scan_index_list, plot_data[left_right + '_data'])
        plot.vlines(plot_data[left_right + '_bag_range'][0], 0, 4, color='red', linestyles='dotted')
        plot.vlines(plot_data[left_right + '_bag_range'][-1], 0, 4, color='red', linestyles='dotted')
        plot.vlines(self.bag_center, 0, 4, color='green', linestyles='dotted')
        plot.show()


if __name__ == '__main__':
    rclpy.init_node('find_bag_node')
    fb = FindBag()
    fb.startUp()
    #rospy.spin()
    #print(fb.bagFocus('all', 180))
    fb.bagGrasp('left')
    #fb.scanPlot('all', 180)

            



def main():
    print('Hi from happymimi_apps2.')


if __name__ == '__main__':
    main()
