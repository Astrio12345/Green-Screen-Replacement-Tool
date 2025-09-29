from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import os
import uuid
import tempfile
from Green_Screen import GreenScreenProcessor  # Import your modified class

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Initialize processor
processor = GreenScreenProcessor()

# Create upload folders
folders = processor.create_upload_folders(app.root_path)
UPLOAD_FOLDER = folders['uploads']
OUTPUT_FOLDER = folders['outputs']
TEMP_FOLDER = folders['temp']

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER


@app.route('/')
def index():
    """Main page with file upload form"""
    return render_template('Green.html')


@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and start processing"""
    try:
        # Check if files are present
        if 'video' not in request.files or 'background' not in request.files:
            return jsonify({'error': 'Both video and background files are required'}), 400

        video_file = request.files['video']
        background_file = request.files['background']

        # Check if files are selected
        if video_file.filename == '' or background_file.filename == '':
            return jsonify({'error': 'Please select both files'}), 400

        # Save files
        video_path = processor.save_uploaded_file(video_file, UPLOAD_FOLDER)
        background_path = processor.save_uploaded_file(background_file, UPLOAD_FOLDER)

        if not video_path or not background_path:
            return jsonify({'error': 'Invalid file format. Please use supported formats.'}), 400

        # Generate task ID and output path
        task_id = str(uuid.uuid4())
        output_filename = f"processed_{task_id}.mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        # Start processing in background
        processor.process_video_async(video_path, background_path, output_path, task_id)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Files uploaded successfully. Processing started...'
        })

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/progress/<task_id>')
def get_progress(task_id):
    """Get processing progress for a specific task"""
    try:
        progress = processor.get_progress(task_id)
        result = processor.get_result(task_id)

        response_data = {
            'progress': round(progress, 1),
            'completed': result is not None
        }

        if result:
            response_data['result'] = result
            if result['success']:
                response_data['download_url'] = url_for('download_video', task_id=task_id)

        return jsonify(response_data)

    except Exception as e:
        return jsonify({'error': f'Error getting progress: {str(e)}'}), 500


@app.route('/download/<task_id>')
def download_video(task_id):
    """Download the processed video"""
    try:
        result = processor.get_result(task_id)

        if result and result['success'] and os.path.exists(result['output_path']):
            return send_file(
                result['output_path'],
                as_attachment=True,
                download_name=f'green_screen_processed_{task_id}.mp4',
                mimetype='video/mp4'
            )
        else:
            return jsonify({'error': 'Video not ready or processing failed'}), 404

    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500


@app.route('/preview/<task_id>')
def preview_video(task_id):
    """Stream video for preview"""
    try:
        result = processor.get_result(task_id)

        if result and result['success'] and os.path.exists(result['output_path']):
            return send_file(
                result['output_path'],
                mimetype='video/mp4'
            )
        else:
            return jsonify({'error': 'Video not ready'}), 404

    except Exception as e:
        return jsonify({'error': f'Preview failed: {str(e)}'}), 500


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    return jsonify({'error': 'File too large. Maximum size is 500MB.'}), 413


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    return jsonify({'error': 'Internal server error occurred.'}), 500


if __name__ == '__main__':
    # Create required directories
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(TEMP_FOLDER, exist_ok=True)

    print("Starting Green Screen Web Application...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)