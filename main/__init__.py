import random
import string


# --------------------------
# Utility: Generate secret login code
# --------------------------
def generate_secret_code(length=6):
    """
    Generate a secure, uppercase alphanumeric login code.
    Default length is 6 characters.
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))
