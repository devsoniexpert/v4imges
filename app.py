from flask import Flask, request, jsonify
from PIL import Image
import requests
from io import BytesIO

app = Flask(__name__)

@app.route('/process', methods=['GET'])
def process_image():
    image_url = request.args.get('url')
    resolution_step = int(request.args.get('res', 1)) 
    
    if not image_url:
        return jsonify({"success": False, "error": "No URL provided."})

    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert('RGB')
        
        max_base_width = 150
        if img.width > max_base_width:
            ratio = max_base_width / float(img.width)
            new_height = int(float(img.height) * float(ratio))
            img = img.resize((max_base_width, new_height), Image.Resampling.LANCZOS)
        
        if resolution_step > 1:
            img = img.resize(
                (max(1, img.width // resolution_step), max(1, img.height // resolution_step)), 
                Image.Resampling.NEAREST
            )
        
        pixels = []
        width, height = img.size
        
        for y in range(height):
            for x in range(width):
                r, g, b = img.getpixel((x, y))
                if r > 245 and g > 245 and b > 245: # Skips white backgrounds
                    continue
                    
                pixels.append({
                    "x": x,
                    "y": height - y, 
                    "c": [r/255.0, g/255.0, b/255.0]
                })
                
        return jsonify({
            "success": True, 
            "width": width, 
            "height": height, 
            "total_blocks": len(pixels),
            "pixels": pixels
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000
