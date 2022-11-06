"""
Classic cart-pole system implemented by Rich Sutton et al.
Copied from http://incompleteideas.net/sutton/book/code/pole.c
permalink: https://perma.cc/C9ZM-652R
"""

import math
import gym
from gym import spaces, logger
from gym.utils import seeding
import numpy as np


class MyEnv(gym.Env):
    """
    Description:
        A pole is attached by an un-actuated joint to a cart, which moves along
        a frictionless track. The pendulum starts upright, and the goal is to
        prevent it from falling over by increasing and reducing the cart's
        velocity.

    Source:
        This environment corresponds to the version of the cart-pole problem
        described by Barto, Sutton, and Anderson

    Observation:
        Type: Box(4)
        Num     Observation               Min                     Max
        0       Cart Position             -4.8                    4.8
        1       Cart Velocity             -Inf                    Inf
        2       Pole Angle                -0.418 rad (-24 deg)    0.418 rad (24 deg)
        3       Pole Angular Velocity     -Inf                    Inf

    Actions:
        Type: Discrete(2)
        Num   Action
        0     Push cart to the left
        1     Push cart to the right

        Note: The amount the velocity that is reduced or increased is not
        fixed; it depends on the angle the pole is pointing. This is because
        the center of gravity of the pole increases the amount of energy needed
        to move the cart underneath it

    Reward:
        Reward is 1 for every step taken, including the termination step

    Starting State:
        All observations are assigned a uniform random value in [-0.05..0.05]

    Episode Termination:
        Pole Angle is more than 12 degrees.
        Cart Position is more than 2.4 (center of the cart reaches the edge of
        the display).
        Episode length is greater than 200.
        Solved Requirements:
        Considered solved when the average return is greater than or equal to
        195.0 over 100 consecutive trials.
    """

    metadata = {"render.modes": ["human", "rgb_array"], "video.frames_per_second": 50}

    def __init__(self):
        #self.gravity = 9.8
        #self.masscart = 1.0
        #self.masspole = 0.1
        #self.total_mass = self.masspole + self.masscart
        #self.length = 0.5  # actually half the pole's length
        #self.polemass_length = self.masspole * self.length self.force_mag = 10.0
        #self.tau = 0.02  # seconds between state updates
        #self.kinematics_integrator = "euler"

        # Angle at which to fail the episode
        #self.theta_threshold_radians = 12 * 2 * math.pi / 360
        #self.x_threshold = 2.4

        # Angle limit set to 2 * theta_threshold_radians so failing observation
        # is still within bounds.
        #high = np.array(
        #    [
        #        self.x_threshold * 2,
        #        np.finfo(np.float32).max,
        #        self.theta_threshold_radians * 2,
        #        np.finfo(np.float32).max,
        #    ],
        #    dtype=np.float32,
        #)
        self.N_RESOURCE = 3
        self.N_APP = 3
        self.N_RESOURCE_APP = self.N_RESOURCE * self.N_APP
        self.N_PAIR = self.N_APP * (self.N_APP - 1)

        max_arr = []
        for i_res in range(0, self.N_RESOURCE):
            for i_app in range(0, self.N_APP):
                max_arr.append(np.finfo(np.float32).max)

        high = np.array(max_arr, dtype=np.float32,)
        #high = np.array(
        #    [
        #        np.finfo(np.float32).max,
        #        np.finfo(np.float32).max,
        #        np.finfo(np.float32).max,
        #    ],
        #    dtype=np.float32,
        #)

        self.action_space = spaces.Discrete(self.N_RESOURCE * self.N_PAIR)
        self.observation_space = spaces.Box(-high, high, dtype=np.float32)

        self.seed()
        self.viewer = None
        self.state = None

        self.steps_beyond_done = None

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def step2(self, action):
        err_msg = "%r (%s) invalid" % (action, type(action))
        assert self.action_space.contains(action), err_msg

        x = self.state
        reward = 0.0
        res_id = int(action / (self.N_APP * (self.N_APP - 1)))
        src_app = int(action % (self.N_APP * (self.N_APP - 1)) / (self.N_APP - 1))
        dst_app = action % (self.N_APP - 1)
        print('res_id = %d, src_app = %d, dst_app = %d' % (res_id, src_app, dst_app))
        if dst_app >= src_app:
            dst_app += 1
        src_ind = res_id * self.N_APP + src_app
        dst_ind = res_id * self.N_APP + dst_app
        if self.state[src_ind] > 1:
            self.state[src_ind] -= 1
            self.state[dst_ind] += 1

        rwd = 0.0
        for res_id in range(0, self.N_RESOURCE):
            avg = 0.0
            for app_id in range(0, self.N_APP):
                ind = res_id * self.N_APP + app_id
                avg += self.state[ind]
            avg /= self.N_APP
            for app_id in range(0, self.N_APP):
                ind = res_id * self.N_APP + app_id
                #rwd += (self.state[ind] - avg) ** 2
        #rwd = -rwd

        done = False
        #if rwd > -15:
        #    done = True
        return np.array(self.state, dtype=np.float32), rwd, done, {}

    def step(self, action):
        err_msg = "%r (%s) invalid" % (action, type(action))
        assert self.action_space.contains(action), err_msg

        x = self.state
        reward = 0.0
        res_id = int(action / (self.N_APP * (self.N_APP - 1)))
        src_app = int(action % (self.N_APP * (self.N_APP - 1)) / (self.N_APP - 1))
        dst_app = action % (self.N_APP - 1)
        print('res_id = %d, src_app = %d, dst_app = %d' % (res_id, src_app, dst_app))
        if dst_app >= src_app:
            dst_app += 1
        src_ind = res_id * self.N_APP + src_app
        dst_ind = res_id * self.N_APP + dst_app
        if self.state[src_ind] > -10 and self.state[dst_ind] < 10:
            self.state[src_ind] -= 1
            self.state[dst_ind] += 1

        rwd = 0.0
        for res_id in range(0, self.N_RESOURCE):
            avg = 0.0
            for app_id in range(0, self.N_APP):
                ind = res_id * self.N_APP + app_id
                avg += self.state[ind]
            avg /= self.N_APP
            for app_id in range(0, self.N_APP):
                ind = res_id * self.N_APP + app_id
                rwd += (self.state[ind] - avg) ** 2
        rwd = -rwd

        done = False
        if rwd > -15:
            done = True
        return np.array(self.state, dtype=np.float32), rwd, done, {}

    def reset(self):
        #self.state = self.np_random.uniform(low=-0.05, high=0.05, size=(4,))
        self.state = self.np_random.uniform(low=-10, high=10, size=(self.N_RESOURCE * self.N_APP,))
        self.steps_beyond_done = None
        return np.array(self.state, dtype=np.float32)

    def render(self, mode="human"):
        screen_width = 600
        screen_height = 400

        world_width = self.x_threshold * 2
        scale = screen_width / world_width
        carty = 100  # TOP OF CART
        polewidth = 10.0
        polelen = scale * (2 * self.length)
        cartwidth = 50.0
        cartheight = 30.0

        if self.viewer is None:
            from gym.envs.classic_control import rendering

            self.viewer = rendering.Viewer(screen_width, screen_height)
            l, r, t, b = -cartwidth / 2, cartwidth / 2, cartheight / 2, -cartheight / 2
            axleoffset = cartheight / 4.0
            cart = rendering.FilledPolygon([(l, b), (l, t), (r, t), (r, b)])
            self.carttrans = rendering.Transform()
            cart.add_attr(self.carttrans)
            self.viewer.add_geom(cart)
            l, r, t, b = (
                -polewidth / 2,
                polewidth / 2,
                polelen - polewidth / 2,
                -polewidth / 2,
            )
            pole = rendering.FilledPolygon([(l, b), (l, t), (r, t), (r, b)])
            pole.set_color(0.8, 0.6, 0.4)
            self.poletrans = rendering.Transform(translation=(0, axleoffset))
            pole.add_attr(self.poletrans)
            pole.add_attr(self.carttrans)
            self.viewer.add_geom(pole)
            self.axle = rendering.make_circle(polewidth / 2)
            self.axle.add_attr(self.poletrans)
            self.axle.add_attr(self.carttrans)
            self.axle.set_color(0.5, 0.5, 0.8)
            self.viewer.add_geom(self.axle)
            self.track = rendering.Line((0, carty), (screen_width, carty))
            self.track.set_color(0, 0, 0)
            self.viewer.add_geom(self.track)

            self._pole_geom = pole

        if self.state is None:
            return None

        # Edit the pole polygon vertex
        pole = self._pole_geom
        l, r, t, b = (
            -polewidth / 2,
            polewidth / 2,
            polelen - polewidth / 2,
            -polewidth / 2,
        )
        pole.v = [(l, b), (l, t), (r, t), (r, b)]

        x = self.state
        cartx = x[0] * scale + screen_width / 2.0  # MIDDLE OF CART
        self.carttrans.set_translation(cartx, carty)
        self.poletrans.set_rotation(-x[2])

        return self.viewer.render(return_rgb_array=mode == "rgb_array")

    def close(self):
        if self.viewer:
            self.viewer.close()
            self.viewer = None
