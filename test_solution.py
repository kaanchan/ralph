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
    current_loss = float('inf')

    for epoch in range(epochs):
        total_loss = 0
        for i in range(len(xor_inputs)):
            input_data = xor_inputs[i]
            target_output = xor_outputs[i]

            # Forward pass
            output = nn.forward(input_data)

            # Calculate error and total loss (Mean Squared Error)
            error = [target_output[j] - output[j] for j in range(len(output))]
            total_loss += sum([e*e for e in error]) / len(error)

            # Backward pass (backpropagation)
            nn.backward(input_data, target_output, learning_rate)
        
        current_loss = total_loss / len(xor_inputs)
        if current_loss < min_loss:
            break
    
    assert current_loss < min_loss, f"Neural network failed to train XOR under {min_loss} loss within {epochs} epochs. Final loss: {current_loss}"
