import random
import codecs

def get_random_context_segment(context, cutoff):
    # split the context segment into words and randomly choose a segment of those words based on the cuttoff
    context_words = context.split(" ")
    start_point = random.choice(range(0, max(len(context_words) - cutoff, 1)))
    return " ".join(context_words[start_point:min(start_point+cutoff, len(context_words))]) + "\n"

with open("C:/Users/xande/Programming Files/Winter Python Lessons/Quizzy/context.txt", "r", encoding="utf-8") as file:
    context = file.read()
print(get_random_context_segment(context, 500))
context = input("")