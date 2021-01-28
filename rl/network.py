import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

torch.set_printoptions(precision=5)

if torch.cuda.is_available():
    device = torch.device('cuda')
else:
    device = torch.device('cpu')

print("starting using device", device)


class RLModule(nn.Module):
    def __init__(self, /, n_cats, input_size, emb_size, out_size):
        super(RLModule, self).__init__()
        self.n_cats = n_cats
        self.input_size = input_size
        self.emb_size = emb_size
        self.out_size = out_size

        self.embedding = nn.Embedding(n_cats, emb_size).to(device)
        self.layer_1 = nn.Linear(emb_size * input_size, out_size).to(device)

    def run(self, x):
        batch_size, input_size = x.shape
        assert input_size == self.input_size

        x = self.embedding(x)
        x = x.reshape(batch_size, input_size * self.emb_size)
        x = self.layer_1(x)

        return x

