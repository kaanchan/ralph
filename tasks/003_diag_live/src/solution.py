def is_palindrome(s):
    # Normalize the string by removing spaces and converting to lowercase
    normalized_str = s.replace(" ", "").lower()
    # Check if the string reads the same forwards and backwards
    return normalized_str == normalized_str[::-1]
