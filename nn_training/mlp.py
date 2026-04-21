from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


def relu_grad(x: np.ndarray) -> np.ndarray:
    return (x > 0.0).astype(np.float32)


def silu(x: np.ndarray) -> np.ndarray:
    sig = 1.0 / (1.0 + np.exp(-x))
    return x * sig


def silu_grad(x: np.ndarray) -> np.ndarray:
    sig = 1.0 / (1.0 + np.exp(-x))
    return sig * (1.0 + x * (1.0 - sig))


@dataclass
class TrainingResult:
    train_loss: float
    val_loss: float
    epochs: int


class Normalization:
    def __init__(self, means: np.ndarray, stds: np.ndarray) -> None:
        self.means = means.astype(np.float32)
        self.stds = np.where(stds == 0.0, 1.0, stds).astype(np.float32)

    @classmethod
    def fit(cls, inputs: np.ndarray) -> "Normalization":
        if len(inputs) == 0:
            return cls(np.zeros((inputs.shape[1],), dtype=np.float32), np.ones((inputs.shape[1],), dtype=np.float32))
        return cls(inputs.mean(axis=0), inputs.std(axis=0))

    def transform(self, inputs: np.ndarray) -> np.ndarray:
        return (inputs - self.means) / self.stds

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"means": self.means.tolist(), "stds": self.stds.tolist()}, indent=2),
            encoding="utf-8",
        )


class SimpleMLP:
    def __init__(
        self,
        input_dim: int,
        hidden_dims: list[int],
        output_dim: int,
        activation: str = "relu",
        output_activation: str = "linear",
        seed: int = 7,
    ) -> None:
        rng = np.random.default_rng(seed)
        dims = [input_dim, *hidden_dims, output_dim]
        self.weights: list[np.ndarray] = []
        self.biases: list[np.ndarray] = []
        self.activation_name = activation
        self.output_activation_name = output_activation
        for in_dim, out_dim in zip(dims[:-1], dims[1:]):
            scale = np.sqrt(2.0 / max(in_dim, 1))
            self.weights.append((rng.standard_normal((in_dim, out_dim)) * scale).astype(np.float32))
            self.biases.append(np.zeros((out_dim,), dtype=np.float32))

    def _activation(self, values: np.ndarray) -> np.ndarray:
        if self.activation_name == "silu":
            return silu(values)
        return relu(values)

    def _activation_grad(self, values: np.ndarray) -> np.ndarray:
        if self.activation_name == "silu":
            return silu_grad(values)
        return relu_grad(values)

    def _output_activation(self, values: np.ndarray) -> np.ndarray:
        if self.output_activation_name == "tanh":
            return np.tanh(values)
        return values

    def _output_activation_grad(self, values: np.ndarray) -> np.ndarray:
        if self.output_activation_name == "tanh":
            activated = np.tanh(values)
            return 1.0 - activated * activated
        return np.ones_like(values, dtype=np.float32)

    def forward(self, inputs: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray], np.ndarray]:
        activations = [inputs]
        pre_activations = []
        x = inputs
        for index, (weights, biases) in enumerate(zip(self.weights, self.biases)):
            z = x @ weights + biases
            pre_activations.append(z)
            if index == len(self.weights) - 1:
                x = self._output_activation(z)
            else:
                x = self._activation(z)
            activations.append(x)
        return activations, pre_activations, x

    def predict(self, inputs: np.ndarray) -> np.ndarray:
        _, _, outputs = self.forward(inputs)
        return outputs

    def train(
        self,
        train_x: np.ndarray,
        train_y: np.ndarray,
        val_x: np.ndarray,
        val_y: np.ndarray,
        *,
        epochs: int = 300,
        learning_rate: float = 1e-3,
        batch_size: int = 128,
        weight_decay: float = 1e-5,
    ) -> TrainingResult:
        if len(train_x) == 0:
            return TrainingResult(train_loss=0.0, val_loss=0.0, epochs=0)

        m_w = [np.zeros_like(weights) for weights in self.weights]
        v_w = [np.zeros_like(weights) for weights in self.weights]
        m_b = [np.zeros_like(biases) for biases in self.biases]
        v_b = [np.zeros_like(biases) for biases in self.biases]
        beta1 = 0.9
        beta2 = 0.999
        epsilon = 1e-8
        step = 0
        rng = np.random.default_rng(11)

        for _ in range(epochs):
            order = rng.permutation(len(train_x))
            shuffled_x = train_x[order]
            shuffled_y = train_y[order]
            for start in range(0, len(train_x), batch_size):
                batch_x = shuffled_x[start : start + batch_size]
                batch_y = shuffled_y[start : start + batch_size]
                step += 1

                activations, pre_activations, outputs = self.forward(batch_x)
                grad = (2.0 / max(len(batch_x), 1)) * (outputs - batch_y)
                grad *= self._output_activation_grad(pre_activations[-1])

                grad_w: list[np.ndarray] = []
                grad_b: list[np.ndarray] = []
                for layer in reversed(range(len(self.weights))):
                    grad_w_layer = activations[layer].T @ grad + weight_decay * self.weights[layer]
                    grad_b_layer = grad.sum(axis=0)
                    grad_w.insert(0, grad_w_layer.astype(np.float32))
                    grad_b.insert(0, grad_b_layer.astype(np.float32))
                    if layer > 0:
                        grad = (grad @ self.weights[layer].T) * self._activation_grad(pre_activations[layer - 1])

                for index in range(len(self.weights)):
                    m_w[index] = beta1 * m_w[index] + (1.0 - beta1) * grad_w[index]
                    v_w[index] = beta2 * v_w[index] + (1.0 - beta2) * (grad_w[index] * grad_w[index])
                    m_b[index] = beta1 * m_b[index] + (1.0 - beta1) * grad_b[index]
                    v_b[index] = beta2 * v_b[index] + (1.0 - beta2) * (grad_b[index] * grad_b[index])

                    m_w_hat = m_w[index] / (1.0 - beta1**step)
                    v_w_hat = v_w[index] / (1.0 - beta2**step)
                    m_b_hat = m_b[index] / (1.0 - beta1**step)
                    v_b_hat = v_b[index] / (1.0 - beta2**step)

                    self.weights[index] -= learning_rate * m_w_hat / (np.sqrt(v_w_hat) + epsilon)
                    self.biases[index] -= learning_rate * m_b_hat / (np.sqrt(v_b_hat) + epsilon)

        train_loss = mse(self.predict(train_x), train_y)
        val_loss = mse(self.predict(val_x), val_y) if len(val_x) else train_loss
        return TrainingResult(train_loss=float(train_loss), val_loss=float(val_loss), epochs=epochs)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray | str | int] = {
            "activation": np.asarray(self.activation_name),
            "output_activation": np.asarray(self.output_activation_name),
            "input_dim": np.asarray(self.weights[0].shape[0]),
            "output_dim": np.asarray(self.weights[-1].shape[1]),
            "layer_count": np.asarray(len(self.weights)),
        }
        for index, (weights, biases) in enumerate(zip(self.weights, self.biases)):
            payload[f"W{index}"] = weights
            payload[f"b{index}"] = biases
        np.savez(path, **payload)


def mse(predictions: np.ndarray, targets: np.ndarray) -> float:
    if len(predictions) == 0:
        return 0.0
    diff = predictions - targets
    return float(np.mean(diff * diff))

