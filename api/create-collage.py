# api/create-collage.py - Vercel Python Function for n8n
from http.server import BaseHTTPRequestHandler
import json
import base64
import io
import math
import urllib.request
from PIL import Image, ImageDraw
import ssl

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Enable CORS for n8n
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            # Read request from n8n
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            photo_urls = data.get('photos', [])
            metadata = data.get('metadata', {})
            
            print(f"Creating collage from {len(photo_urls)} photos")
            
            if len(photo_urls) < 2:
                self._send_error("Need at least 2 photos for collage")
                return
            
            # Download and process photos
            images = []
            successful_downloads = 0
            
            # Create SSL context that doesn't verify certificates (for Google Drive)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            for i, url in enumerate(photo_urls):
                try:
                    print(f"Downloading photo {i+1}/{len(photo_urls)}")
                    
                    # Create request with headers
                    req = urllib.request.Request(
                        url, 
                        headers={
                            'User-Agent': 'Mozilla/5.0 (n8n-collage-service)',
                            'Accept': 'image/jpeg,image/png,image/*,*/*'
                        }
                    )
                    
                    # Download image
                    with urllib.request.urlopen(req, context=ssl_context, timeout=30) as response:
                        image_data = response.read()
                    
                    print(f"Downloaded {len(image_data)} bytes")
                    
                    # Open and validate image
                    img = Image.open(io.BytesIO(image_data))
                    
                    # Convert to RGB if needed
                    if img.mode != 'RGB':
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'RGBA':
                            rgb_img.paste(img, mask=img.split()[-1])
                        else:
                            rgb_img.paste(img)
                        img = rgb_img
                    
                    images.append(img)
                    successful_downloads += 1
                    print(f"✅ Successfully processed photo {i+1}")
                    
                except Exception as photo_error:
                    print(f"❌ Failed to process photo {i+1}: {str(photo_error)}")
                    continue
            
            if successful_downloads < 2:
                self._send_error(f"Only {successful_downloads} photos downloaded successfully")
                return
            
            print(f"Creating collage from {successful_downloads} images")
            
            # Create asymmetrical layout
            def create_asymmetrical_layout(num_images):
                layouts = {
                    2: [(2, 1)],
                    3: [(3, 1), (2, 1)],
                    4: [(2, 2)],
                    5: [(3, 1), (2, 1)],
                    6: [(3, 2)],
                    7: [(4, 1), (3, 1)],
                    8: [(4, 2)],
                    9: [(3, 3)],
                    10: [(4, 1), (3, 2)],
                    11: [(4, 1), (4, 1), (3, 1)],
                    12: [(4, 3)],
                }
                
                if num_images <= 12:
                    return layouts.get(num_images, [(4, math.ceil(num_images/4))])
                
                # For larger numbers, create varied row lengths
                rows = []
                remaining = num_images
                while remaining > 0:
                    if remaining >= 4:
                        row_size = 3 + (remaining % 3)
                        if row_size > 5:
                            row_size = 4
                    else:
                        row_size = remaining
                    rows.append((row_size, 1))
                    remaining -= row_size
                
                return rows
            
            layout = create_asymmetrical_layout(successful_downloads)
            
            photo_size = 400
            gap = 15
            border_width = 3
            
            # Calculate canvas dimensions based on layout
            max_cols = max(row[0] for row in layout)
            total_rows = len(layout)
            
            canvas_width = (max_cols * photo_size) + ((max_cols - 1) * gap) + (2 * gap)
            canvas_height = (total_rows * photo_size) + ((total_rows - 1) * gap) + (2 * gap)
            
            # Create white canvas
            collage = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
            draw = ImageDraw.Draw(collage)
            
            # Place images in asymmetrical layout
            img_index = 0
            for row_idx, (cols_in_row, _) in enumerate(layout):
                # Center the row if it has fewer columns than max
                row_offset = (max_cols - cols_in_row) * (photo_size + gap) // 2
                
                for col_idx in range(cols_in_row):
                    if img_index >= len(images):
                        break
                        
                    img = images[img_index]
                    
                    x = gap + row_offset + (col_idx * (photo_size + gap))
                    y = gap + (row_idx * (photo_size + gap))
                    
                    # Resize image to fit
                    img_resized = img.resize((photo_size, photo_size), Image.Resampling.LANCZOS)
                    
                    # Draw border
                    border_color = (220, 220, 220)
                    draw.rectangle(
                        [x - border_width, y - border_width, 
                         x + photo_size + border_width - 1, y + photo_size + border_width - 1],
                        outline=border_color,
                        width=border_width
                    )
                    
                    # Paste image
                    collage.paste(img_resized, (x, y))
                    print(f"Placed image {img_index+1} at position ({x}, {y})")
                    
                    img_index += 1
            
            # Convert to base64
            output_buffer = io.BytesIO()
            collage.save(output_buffer, format='JPEG', quality=92, optimize=True)
            base64_image = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
            
            # Generate filename
            date_str = metadata.get('date', '2025-07-24')
            activity = metadata.get('tipActivitate', 'activity')
            building = metadata.get('cladire', 'building')
            
            filename = f"{date_str}_{activity}_{building}_COLLAGE.jpg"
            filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)
            
            print(f"✅ Collage created: {filename} ({canvas_width}x{canvas_height})")
            
            # Send response to n8n
            response_data = {
                'success': True,
                'image_base64': base64_image,
                'filename': filename,
                'dimensions': {
                    'width': canvas_width,
                    'height': canvas_height
                },
                'photos_processed': successful_downloads,
                'total_photos': len(photo_urls),
                'grid_layout': f"asymmetrical_{total_rows}_rows",
                'file_size_bytes': len(output_buffer.getvalue()),
                'message': f'Collage created successfully with {successful_downloads} photos'
            }
            
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as error:
            print(f"❌ Service error: {str(error)}")
            self._send_error(str(error))
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _send_error(self, message):
        self.send_response(500)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        error_response = {
            'success': False,
            'error': message
        }
        self.wfile.write(json.dumps(error_response).encode())