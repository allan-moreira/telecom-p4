import xml.etree.ElementTree as ET
import re

thickness = 0.2

def parse_svg_path_d(d_string):
    tokens = re.findall(r'[a-zA-Z]|-?\d*\.?\d+', d_string)
    points = []
    current_pos = [0.0, 0.0]
    command = ''
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            command = token
            i += 1
            if command.lower() == 'z':
                break
            continue
        if command.lower() in ['m', 'l']:
            x = float(token)
            y = float(tokens[i+1])
            i += 2
            if command == 'm' and not points:
                current_pos = [x, y]
            elif command == 'L':
                current_pos = [x, y]
            else: # 'l' ou 'm' implícito
                current_pos[0] += x
                current_pos[1] += y
            points.append(tuple(current_pos))
    return points

with open('trena.svg') as f:
    svg_content = f.read()

namespaces = {'svg': 'http://www.w3.org/2000/svg'}
root = ET.fromstring(svg_content)
g_element = root.find('.//svg:g', namespaces)
path_element = g_element.find('svg:path', namespaces)
d_attribute = path_element.get('d')
transform_attribute = g_element.get('transform')
points = parse_svg_path_d(d_attribute)

max_y = max(y for x, y in points)
min_x = min(x for x, y in points)
max_x = max(x for x, y in points)
mid_x = (min_x + max_x) / 2.
points = [(x - mid_x, max_y - y - thickness/2) for x, y in points]

print("points = [" +
    "[" + ",".join(f'{x:.3f}' for x,y in points) + "],"
    "[" + ",".join(f'{y:.3f}' for x,y in points) + "]]")
