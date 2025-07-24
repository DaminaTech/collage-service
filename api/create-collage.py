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
            
            print(f"Creating collages from {successful_downloads} images")
            
            # Split images into chunks of 4
            def chunk_images(images, chunk_size=4):
                for i in range(0, len(images), chunk_size):
                    yield images[i:i + chunk_size]
            
            def create_single_collage(chunk_images, chunk_index, total_chunks):
                num_images = len(chunk_images)
                target_size = 500  # Target size for images
                min_dimension = 350  # Minimum width or height
                max_dimension = 650  # Maximum width or height
                gap = 15
                border_width = 3
                
                # Calculate dimensions for each image while preserving aspect ratio
                processed_images = []
                for img in chunk_images:
                    original_width, original_height = img.size
                    aspect_ratio = original_width / original_height
                    
                    # Scale image to target size while respecting min/max constraints
                    if original_width > original_height:
                        # Landscape - base on width
                        new_width = min(max_dimension, max(min_dimension, target_size))
                        new_height = int(new_width / aspect_ratio)
                        
                        # Ensure height meets minimum
                        if new_height < min_dimension:
                            new_height = min_dimension
                            new_width = int(new_height * aspect_ratio)
                            
                    else:
                        # Portrait or square - base on height
                        new_height = min(max_dimension, max(min_dimension, target_size))
                        new_width = int(new_height * aspect_ratio)
                        
                        # Ensure width meets minimum
                        if new_width < min_dimension:
                            new_width = min_dimension
                            new_height = int(new_width / aspect_ratio)
                    
                    # Final constraint check
                    if new_width > max_dimension:
                        new_width = max_dimension
                        new_height = int(new_width / aspect_ratio)
                    if new_height > max_dimension:
                        new_height = max_dimension
                        new_width = int(new_height * aspect_ratio)
                    
                    # Resize image
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    processed_images.append({
                        'image': img_resized,
                        'width': new_width,
                        'height': new_height
                    })
                
                # Calculate grid layout
                if num_images <= 2:
                    cols, rows = num_images, 1
                elif num_images <= 4:
                    cols, rows = 2, 2
                
                # Calculate cell dimensions more efficiently - use average + padding instead of max
                avg_width = sum(img_data['width'] for img_data in processed_images) / len(processed_images)
                avg_height = sum(img_data['height'] for img_data in processed_images) / len(processed_images)
                
                # Use 110% of average size to reduce empty space while accommodating larger images
                cell_width = int(avg_width * 1.1)
                cell_height = int(avg_height * 1.1)
                
                # Ensure cells are at least as big as the largest image
                cell_width = max(cell_width, max(img_data['width'] for img_data in processed_images))
                cell_height = max(cell_height, max(img_data['height'] for img_data in processed_images))
                
                # Calculate canvas size
                canvas_width = (cols * cell_width) + ((cols - 1) * gap) + (2 * gap)
                canvas_height = (rows * cell_height) + ((rows - 1) * gap) + (2 * gap)
                
                # Create white canvas
                collage = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
                draw = ImageDraw.Draw(collage)
                
                # Place images in grid
                for i, img_data in enumerate(processed_images):
                    if num_images <= 2:
                        # Horizontal layout for 1-2 images
                        col = i
                        row = 0
                    else:
                        # 2x2 grid for 3-4 images
                        col = i % 2
                        row = i // 2
                    
                    # Calculate cell position
                    cell_x = gap + (col * (cell_width + gap))
                    cell_y = gap + (row * (cell_height + gap))
                    
                    # Center image within cell
                    img_width = img_data['width']
                    img_height = img_data['height']
                    x = cell_x + (cell_width - img_width) // 2
                    y = cell_y + (cell_height - img_height) // 2
                    
                    # Draw border around the image (not the cell)
                    border_color = (220, 220, 220)
                    draw.rectangle(
                        [x - border_width, y - border_width, 
                         x + img_width + border_width - 1, y + img_height + border_width - 1],
                        outline=border_color,
                        width=border_width
                    )
                    
                    # Paste image
                    collage.paste(img_data['image'], (x, y))
                    print(f"Placed image {i+1} ({img_width}x{img_height}) at position ({x}, {y}) in collage {chunk_index+1}")
                
                # Convert to base64
                output_buffer = io.BytesIO()
                collage.save(output_buffer, format='JPEG', quality=92, optimize=True)
                base64_image = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
                
                return {
                    'image_base64': base64_image,
                    'dimensions': {'width': canvas_width, 'height': canvas_height},
                    'photos_in_collage': num_images,
                    'file_size_bytes': len(output_buffer.getvalue()),
                    'grid_layout': f"{cols}x{rows}"
                }
            
            # Create multiple collages
            image_chunks = list(chunk_images(images, 4))
            collages = []
            
            # Generate base filename
            date_str = metadata.get('date', '2025-07-24')
            activity = metadata.get('tipActivitate', 'activity')
            building = metadata.get('cladire', 'building')
            
            for i, chunk in enumerate(image_chunks):
                collage_data = create_single_collage(chunk, i, len(image_chunks))
                
                # Generate filename with page number
                if len(image_chunks) > 1:
                    filename = f"{date_str}_{activity}_{building}_COLLAGE_page_{i+1}.jpg"
                else:
                    filename = f"{date_str}_{activity}_{building}_COLLAGE.jpg"
                filename = ''.join(c if c.isalnum() or c in '._-' else '_' for c in filename)
                
                collage_data['filename'] = filename
                collages.append(collage_data)
                
                print(f"✅ Collage {i+1}/{len(image_chunks)} created: {filename} ({collage_data['dimensions']['width']}x{collage_data['dimensions']['height']})")
            
            # Send response to n8n
            response_data = {
                'success': True,
                'collages': collages,
                'total_collages': len(collages),
                'photos_processed': successful_downloads,
                'total_photos': len(photo_urls),
                'message': f'{len(collages)} collage(s) created successfully with {successful_downloads} photos'
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