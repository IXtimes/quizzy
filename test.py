import Levenshtein as lev
from PIL import ImageFont, Image
from options import *
import re
import matplotlib.pyplot as plt
import tkinter as tk
import customtkinter as ctk

def measure_text_width(text):
    font = ImageFont.truetype(resource_path('Resources/tahoma.ttf'), NORMAL_FONT_SIZE)
    width = font.getlength(text)
    return width

def string_similarity(s1, s2):
    """
    Calculates the similarity between two strings using the Levenshtein distance.
    """
    distance = lev.distance(s1, s2)
    max_length = max(len(s1), len(s2))
    similarity = 1 - (distance / max_length)
    return similarity

def remove_backticked_imbeds(s):
    pattern = r'```[\s\S]*?```'
    return re.sub(pattern, "", s)

def render_latex(latex_string):
    # convert to latex
    conv_latex = r"$" + latex_string + "$"
    
    # create an image of the latex expression
    fig = plt.figure(figsize=(6, 1), frameon=False)
    fig.text(0.5, 0.5, conv_latex, size=12, ha='center', va='center')
    plt.axis('off')
    plt.savefig("output.png", bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    
    # open the image with pillow
    output_latex = Image.open("output.png")
    width, height = output_latex.size
    
    # display the image
    global image_label
    image_label = ctk.CTkLabel(window, text="", image=ctk.CTkImage(output_latex, size = (width, height)))
    image_label.pack(before=entry, fill='both', expand=True, padx=10, pady=5)

# Example usage
s1 = "O(n log n)"
s2 = "O(n log n)"
print(f"{s1} is {string_similarity(s1, s2)*100}% similar to {s2}")

