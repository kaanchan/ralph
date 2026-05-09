# solution.py
import random
import math

class NeuralNetwork:
    def __init__(self, input_size, hidden_size, output_size):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        
        # Initialize weights randomly
        self.weights_input_hidden = [[random.uniform(-1, 1) for _ in range(hidden_size)] for _ in range(input_size)]
        self.weights_hidden_output = [[random.uniform(-1, 1) for _ in range(output_size)] for _ in range(hidden_size)]
        
    def sigmoid(self, x):
        # Using math.exp for a more precise exponential calculation.
        return 1 / (1 + math.exp(-x))
    
    def sigmoid_derivative(self, x):
        return x * (1 - x)
    
    def forward(self, inputs):
        self.hidden_layer_input = [sum(inputs[i] * self.weights_input_hidden[i][j] for i in range(self.input_size)) for j in range(self.hidden_size)]
        self.hidden_layer_output = [self.sigmoid(x) for x in self.hidden_layer_input]
        
        self.output_layer_input = [sum(self.hidden_layer_output[j] * self.weights_hidden_output[j][k] for j in range(self.hidden_size)) for k in range(self.output_size)]
        self.output_layer_output = [self.sigmoid(x) for x in self.output_layer_input]
        
        return self.output_layer_output
    
    def backward(self, inputs, targets, learning_rate):
        # Calculate the error
        output_error = [targets[i] - self.output_layer_output[i] for i in range(self.output_size)]
        output_delta = [output_error[i] * self.sigmoid_derivative(self.output_layer_output[i]) for i in range(self.output_size)]
        
        hidden_error = [sum(output_delta[k] * self.weights_hidden_output[j][k] for k in range(self.output_size)) for j in range(self.hidden_size)]
        hidden_delta = [hidden_error[j] * self.sigmoid_derivative(self.hidden_layer_output[j]) for j in range(self.hidden_size)]
        
        # Update weights
        for i in range(self.input_size):
            for j in range(self.hidden_size):
                self.weights_input_hidden[i][j] += learning_rate * inputs[i] * hidden_delta[j]
        
        for j in range(self.hidden_size):
            for k in range(self.output_size):
                self.weights_hidden_output[j][k] += learning_rate * self.hidden_layer_output[j] * output_delta[k]
    
    def train(self, data, labels, learning_rate, epochs):
        for epoch in range(epochs):
            total_error = 0
            for inputs, target in zip(data, labels):
                outputs = self.forward(inputs)
                total_error += sum((target[i] - outputs[i]) ** 2 for i in range(len(target)))
                self.backward(inputs, target, learning_rate)

            if epoch % 100 == 0:
                print(f"Epoch {epoch}, Loss: {total_error:.4f}")

            if total_error < 0.1:
                print(f"Epoch {epoch}, Loss: {total_error:.4f} (Converged)")
                break
        return total_error
