from solution import NeuralNetwork

def test_xor_training():
    # XOR dataset
    # Inputs: [0,0], [0,1], [1,0], [1,1]
    # Outputs: [0], [1], [1], [0]
    xor_inputs = [
        [0, 0],
        [0, 1],
        [1, 0],
        [1, 1]
    ]
    xor_outputs = [
        [0],
        [1],
        [1],
        [0]
    ]

    # Initialize neural network: 2 input neurons, 2 hidden neurons, 1 output neuron
    nn = NeuralNetwork(input_size=2, hidden_size=2, output_size=1)

    learning_rate = 0.5
    epochs = 1000
    min_loss = 0.1

    final_loss = nn.train(xor_inputs, xor_outputs, learning_rate, epochs)
    
    assert final_loss < min_loss, f"Neural network failed to train XOR under {min_loss} loss within {epochs} epochs. Final loss: {final_loss}"
