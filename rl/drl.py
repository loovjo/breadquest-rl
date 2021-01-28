import os, time
import random

import asyncio, aiohttp
from bq_interface import register_user, Action, TileType
from network import RLModule, device

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

N_INSTANCES = 32

FUTURE_DISCOUNT = 0.8

V_SIZE = 5

BATCH_SIZE = 24

SAVE_DIR = "network"

EPSILON = 1e-2

class RLLearning:
    def __init__(self, radius):
        self.radius = radius
        self.side_length = 1 + 2 * self.radius
        self.input_size = self.side_length ** 2
        self.network = RLModule(
            n_cats=len(list(TileType)),
            input_size=self.input_size,
            emb_size=3,
            out_size=len(list(Action)),
        )

        self.sars_idx = 0
        self.states = torch.LongTensor(BATCH_SIZE, N_INSTANCES, self.input_size)
        self.actions = torch.LongTensor(BATCH_SIZE, N_INSTANCES)
        self.scores = torch.FloatTensor(BATCH_SIZE, N_INSTANCES)

        self.crit = nn.MSELoss()
        self.opt = torch.optim.Adam(
            list(self.network.parameters()),
            lr=0.1,
        )

    def load_from_save(self, save_dir):
        net_path = os.path.join(save_dir, "network.pth")
        opt_path = os.path.join(save_dir, "opt.pth")
        if os.path.isfile(net_path) and os.path.isfile(opt_path):
            self.network.load_state_dict(torch.load(net_path, map_location=device))
            self.opt.load_state_dict(torch.load(opt_path, map_location=device))
            print("Loaded save!")
        else:
            print("No save data found :(")

    def save(self, save_dir):
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)

        net_path = os.path.join(save_dir, "network.pth")
        opt_path = os.path.join(save_dir, "opt.pth")
        torch.save(self.network.state_dict(), net_path)
        torch.save(self.opt.state_dict(), opt_path)
        print("Saved!")

    def get_input_from_client(self, client):
        cmap = torch.LongTensor(self.side_length, self.side_length)

        for y in range(-self.radius, self.radius + 1):
            for x in range(-self.radius, self.radius + 1):
                if (x, y) in client.world:
                    cmap[y, x] = TileType.get_category(client.world[(x, y)], client.avatar).value
                else:
                    cmap[y, x] = 100000

        return cmap.flatten()

    def choose_actions(self, state):
        rewards = self.network.run(state)
        dist = rewards.softmax(dim=1)
        dist += EPSILON
        choices = torch.multinomial(dist, 1)[:, 0]
        return choices

    # All before action was performed
    def observe(self, score, state, action):
        self.states[self.sars_idx]  = torch.LongTensor(state)
        self.actions[self.sars_idx] = torch.LongTensor(action)
        self.scores[self.sars_idx]  = torch.FloatTensor(score)

        self.sars_idx += 1

        if self.sars_idx >= BATCH_SIZE:
            self.train_sars()
            self.sars_idx = 0

    def train_sars(self):
        state_t =  self.states[:-1].reshape(N_INSTANCES * (BATCH_SIZE-1), -1)
        action_t = self.actions[:-1].reshape(N_INSTANCES * (BATCH_SIZE-1))
        reward_t = (self.scores[1:] - self.scores[:-1]).reshape(N_INSTANCES * (BATCH_SIZE-1))
        state_t1 = self.states[1:].reshape(N_INSTANCES * (BATCH_SIZE-1), -1)

        self.network.zero_grad()

        q_a_t1 = self.network.run(state_t1)
        q_t = reward_t + q_a_t1.max(dim=1).values * FUTURE_DISCOUNT

        predicted_a = self.network.run(state_t)
        predicted = predicted_a[torch.arange(predicted_a.size(0)), action_t]

        loss = self.crit(predicted, q_t)
        loss.backward()
        print("Training on", state_t.size(0), "samples")
        print("Loss:".rjust(16), loss.item())
        print("Average q:".rjust(16), q_t.mean().item())
        print("Average predicted q:".rjust(16), predicted.mean().item())
        print("Average reward:".rjust(16), reward_t.mean().item())
        self.opt.step()

async def run(clients):
    learner = RLLearning(V_SIZE)
    learner.load_from_save(SAVE_DIR)

    last_save_time = time.time()
    try:
        while True:
            await asyncio.gather(*[
                cl.update_world()
                for cl in clients
            ])
            scores = np.array([cl.get_score() for cl in clients])
            inputs = torch.cat([
                learner.get_input_from_client(cl).unsqueeze(0)
                for cl in clients
            ], dim=0)
            actions = learner.choose_actions(inputs)
            learner.observe(scores, inputs, actions)

            await asyncio.gather(*[
                cl.perform_action(Action(action.item()))
                for action, cl in zip(actions, clients)
            ])
            if time.time() - last_save_time > 30:
                learner.save(SAVE_DIR)
                last_save_time = time.time()
    except KeyboardInterrupt as e:
        learner.save(SAVE_DIR)


async def start_n_more_clients(clients, n):
    if n == 0:
        await run(clients)
    else:
        async with aiohttp.ClientSession() as sess, \
            register_user(V_SIZE, sess, f"smartboix-{n}", f"aaaaa", avatar=random.randrange(0, 8)) as cl:
            # await asyncio.sleep(0.2)
            await start_n_more_clients(clients + [cl], n - 1)

async def main():
    await start_n_more_clients([], N_INSTANCES)

if __name__ == "__main__":
    asyncio.run(main())
