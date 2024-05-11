def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb_color):
    return '#{:02x}{:02x}{:02x}'.format(*rgb_color)

def lerp_color(hex_color1, hex_color2, amount):
    rgb_color1 = hex_to_rgb(hex_color1)
    rgb_color2 = hex_to_rgb(hex_color2)

    r = int(rgb_color1[0] + amount * (rgb_color2[0] - rgb_color1[0]))
    g = int(rgb_color1[1] + amount * (rgb_color2[1] - rgb_color1[1]))
    b = int(rgb_color1[2] + amount * (rgb_color2[2] - rgb_color1[2]))

    return rgb_to_hex((r, g, b))

def lerp_colors(hex_colors, amount):
    n = len(hex_colors)
    if n == 1:
        return hex_colors[0]
    elif n == 2:
        return lerp_color(hex_colors[0], hex_colors[1], amount)
    else:
        sub_amount = amount * n
        idx = min(int(sub_amount), n - 1)
        sub_amount -= idx
        return lerp_color(hex_colors[idx], hex_colors[min(idx + 1, n - 1)], sub_amount)
