from flask import Flask, request, jsonify
from PIL import Image
import requests
from io import BytesIO

app = Flask(__name__)

def colors_match(c1, c2, threshold):
    # Threshold 1 = exact match. Threshold 10 = loose match.
    if threshold == 1:
        return c1 == c2
    max_diff = (threshold - 1) * 12 # Increases tolerance based on slider
    return abs(c1[0]-c2[0]) + abs(c1[1]-c2[1]) + abs(c1[2]-c2[2]) <= max_diff

@app.route('/process', methods=['GET'])
def process_image():
    image_url = request.args.get('url')
    res_step = int(request.args.get('res', 1))
    optimize = request.args.get('opt', 'false').lower() == 'true'
    threshold = int(request.args.get('thresh', 1))
    nobg = request.args.get('nobg', 'false').lower() == 'true'
    
    if not image_url:
        return jsonify({"success": False, "error": "No URL provided."})

    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert('RGBA')
        
        # 1. Background Removal
        if nobg:
            try:
                from rembg import remove
                img = remove(img)
            except ImportError:
                return jsonify({"success": False, "error": "Please run: pip install rembg"})
        
        # 2. Hard scaling limit
        max_base_width = 150
        if img.width > max_base_width:
            ratio = max_base_width / float(img.width)
            new_height = int(float(img.height) * float(ratio))
            img = img.resize((max_base_width, new_height), Image.Resampling.LANCZOS)
        
        # 3. User Resolution Scaling
        if res_step > 1:
            img = img.resize(
                (max(1, img.width // res_step), max(1, img.height // res_step)), 
                Image.Resampling.NEAREST
            )
        
        width, height = img.size
        blocks = []
        
        # 4. Greedy Meshing Optimization
        if optimize:
            visited = [[False for _ in range(width)] for _ in range(height)]
            for y in range(height):
                for x in range(width):
                    if visited[y][x]: continue
                    r, g, b, a = img.getpixel((x, y))
                    
                    # Skip fully transparent pixels or pure white (if bg removal is off)
                    if a < 10 or (r > 245 and g > 245 and b > 245 and not nobg):
                        continue
                    
                    base_color = (r, g, b)
                    
                    # Expand horizontally (X)
                    w = 0
                    while x + w < width and not visited[y][x+w]:
                        nr, ng, nb, na = img.getpixel((x+w, y))
                        if na < 10 or not colors_match(base_color, (nr, ng, nb), threshold):
                            break
                        w += 1
                    
                    # Expand vertically (Y) based on the established width
                    h = 0
                    can_expand_down = True
                    while y + h < height and can_expand_down:
                        for ix in range(w):
                            if visited[y+h][x+ix]:
                                can_expand_down = False
                                break
                            nr, ng, nb, na = img.getpixel((x+ix, y+h))
                            if na < 10 or not colors_match(base_color, (nr, ng, nb), threshold):
                                can_expand_down = False
                                break
                        if can_expand_down:
                            h += 1
                    
                    if h == 0: h = 1
                    
                    # Mark rectangle as visited
                    for dy in range(h):
                        for dx in range(w):
                            visited[y+dy][x+dx] = True
                    
                    # Calculate center coordinates for Roblox CFrame
                    center_x = x + (w - 1) / 2.0
                    center_y = (height - 1) - (y + (h - 1) / 2.0)
                    
                    blocks.append({
                        "x": center_x, "y": center_y,
                        "w": w, "h": h,
                        "c": [base_color[0]/255.0, base_color[1]/255.0, base_color[2]/255.0]
                    })
        else:
            # Traditional 1x1 Rendering
            for y in range(height):
                for x in range(width):
                    r, g, b, a = img.getpixel((x, y))
                    if a < 10 or (r > 245 and g > 245 and b > 245 and not nobg): continue
                    blocks.append({
                        "x": x, "y": height - 1 - y,
                        "w": 1, "h": 1,
                        "c": [r/255.0, g/255.0, b/255.0]
                    })
                
        return jsonify({
            "success": True, 
            "width": width, 
            "height": height, 
            "total_blocks": len(blocks),
            "pixels": blocks
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
