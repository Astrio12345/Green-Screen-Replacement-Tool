import cv2
import numpy as np
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
from threading import Thread
import time


class GreenScreenProcessor:
    def __init__(self):
        self.progress = {}
        self.results = {}

    def allowed_file(self, filename, file_type='video'):
        """Check if file extension is allowed"""
        if file_type == 'video':
            allowed_extensions = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'}
        else:  # image
            allowed_extensions = {'jpg', 'jpeg', 'png', 'bmp', 'tiff'}

        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in allowed_extensions

    def save_uploaded_file(self, file, upload_folder):
        """Save uploaded file and return the path"""
        if file and self.allowed_file(file.filename, 'video' if 'video' in str(file.content_type) else 'image'):
            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            return filepath
        return None

    def replace_green_screen(self, video_path, background_path, output_path, task_id):
        """
        Replace green screen in video with background image
        """
        try:
            # Initialize progress
            self.progress[task_id] = 0

            # Load background image
            background = cv2.imread(background_path)
            if background is None:
                self.results[task_id] = {'success': False, 'error': f'Could not load background image'}
                return False

            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.results[task_id] = {'success': False, 'error': f'Could not open video file'}
                return False

            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"Video properties: {width}x{height}, {fps} FPS, {total_frames} frames")

            # Resize background to match video dimensions
            background = cv2.resize(background, (width, height))

            # Setup video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

            frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert BGR to HSV for better green detection
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                # Define range for green color in HSV
                lower_green = np.array([35, 40, 40])
                upper_green = np.array([85, 255, 255])

                # Create mask for green pixels
                mask = cv2.inRange(hsv, lower_green, upper_green)

                # Apply morphological operations to clean up the mask
                kernel = np.ones((3, 3), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

                # Apply Gaussian blur to soften mask edges
                mask = cv2.GaussianBlur(mask, (5, 5), 0)

                # Normalize mask to 0-1 range for blending
                mask_norm = mask.astype(float) / 255

                # Create 3-channel mask
                mask_3d = np.stack([mask_norm, mask_norm, mask_norm], axis=2)

                # Blend frame and background
                result = frame * (1 - mask_3d) + background * mask_3d
                result = result.astype(np.uint8)

                # Write frame to output video
                out.write(result)

                frame_count += 1

                # Update progress
                progress = (frame_count / total_frames) * 100
                self.progress[task_id] = progress

                if frame_count % 30 == 0:  # Progress update every 30 frames
                    print(f"Processing: {progress:.1f}% complete")

            # Release everything
            cap.release()
            out.release()
            cv2.destroyAllWindows()

            # Mark as completed
            self.progress[task_id] = 100
            self.results[task_id] = {
                'success': True,
                'output_path': output_path,
                'message': 'Green screen replacement completed successfully!'
            }

            print(f"Green screen replacement completed! Output saved as: {output_path}")
            return True

        except Exception as e:
            self.results[task_id] = {'success': False, 'error': str(e)}
            return False

    def process_video_async(self, video_path, background_path, output_path, task_id):
        """Process video in a separate thread"""
        thread = Thread(target=self.replace_green_screen,
                        args=(video_path, background_path, output_path, task_id))
        thread.daemon = True
        thread.start()
        return thread

    def get_progress(self, task_id):
        """Get processing progress for a task"""
        return self.progress.get(task_id, 0)

    def get_result(self, task_id):
        """Get processing result for a task"""
        return self.results.get(task_id, None)

    def cleanup_files(self, *file_paths):
        """Clean up temporary files"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up: {file_path}")
            except Exception as e:
                print(f"Error cleaning up {file_path}: {e}")

    def create_upload_folders(self, base_path):
        """Create necessary folders for file uploads"""
        folders = ['uploads', 'outputs', 'temp']
        created_folders = {}

        for folder in folders:
            folder_path = os.path.join(base_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            created_folders[folder] = folder_path

        return created_folders
