import random
import string
def random_word(length=64):
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(length)])