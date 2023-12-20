import os
import shutil
from flask import Flask, render_template, request, send_file, flash, url_for, redirect, session
import uuid
import subprocess
import time
from threading import Thread, Event  

app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'uploads'
RAR_FOLDER = 'downloads'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RAR_FOLDER'] = RAR_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if not os.path.exists(RAR_FOLDER):
    os.makedirs(RAR_FOLDER)

# Dictionary to store last access time for each user
user_last_access = {}

# Event to signal the cleanup thread to stop
stop_cleanup_thread = Event()

def get_unique_filename(user_folder, filename):
    base, ext = os.path.splitext(filename)
    unique_filename = filename
    counter = 1

    while os.path.exists(os.path.join(user_folder, unique_filename)):
        unique_filename = f"{base}_{counter}{ext}"
        counter += 1

    return unique_filename


def check_inactive_users():
    current_time = time.time()
    inactive_threshold = 1  # Adjust the threshold  

    for user_id, last_access_time in list(user_last_access.items()):
        if current_time - last_access_time > inactive_threshold:
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
            try:
                shutil.rmtree(user_folder)
                print(f'Deleted folder for inactive user {user_id}')
                del user_last_access[user_id]
            except Exception as e:
                print(f'Error deleting folder for inactive user {user_id}: {e}')

def periodic_folder_cleanup():
    while not stop_cleanup_thread.is_set():
        time.sleep(60)  # Adjust the interval as needed 
        check_inactive_users()

# Start a background thread for periodic folder cleanup
cleanup_thread = Thread(target=periodic_folder_cleanup)
cleanup_thread.daemon = True
cleanup_thread.start()


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    user_id = session.get('user_id', None)
    if user_id is not None:
        # Update last access time for the user
        user_last_access[user_id] = time.time()

    return 'OK'

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))

    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

    user_id = session['user_id']

    # Update last access time for the user
    # user_last_access[user_id] = time.time()

    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)

    print(f'User ID: {user_id}')
    print(f'User Folder: {user_folder}')

    if not os.path.exists(user_folder):
        os.makedirs(user_folder)

    unique_filename = get_unique_filename(user_folder, file.filename)

    file_path = os.path.join(user_folder, unique_filename)
    # Save the file in the user-specific folder with the unique filename
    file.save(file_path)

    flash(f'File {unique_filename} uploaded successfully', 'success')
    return redirect(url_for('index'))


@app.route('/download')
def download():
    user_id = session.get('user_id', None)
    if user_id is None:
        flash('No user session found', 'error')
        return redirect(url_for('index'))

    # Update last access time for the user
    # user_last_access[user_id] = time.time()

    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    rar_filename = os.path.join(app.config['RAR_FOLDER'], f'{user_id}_files.rar')

    # Rar the user folder using subprocess.Popen
    with subprocess.Popen(
        ['rar', 'a', rar_filename, user_folder],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # Use text mode to capture output as strings
    ) as process:
        # Capture the output and error streams
        output, error = process.communicate()

        # Check the return code
        return_code = process.returncode

        if output:
            print(f'Rar Output: {output}')
        if error:
            print(f'Rar Error: {error}')

    # Check the return code and handle accordingly
    if return_code == 0:
        return send_file(rar_filename, as_attachment=True)
    else:
        flash(f'Rar command failed with return code {return_code}', 'error')
        return redirect(url_for('index'))

@app.route('/delete_folder', methods=['POST'])
def delete_folder():
    user_id = session.get('user_id', None)
    if user_id:
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        if os.path.exists(user_folder):
            try:
                shutil.rmtree(user_folder)
                print(f'Deleted folder for user {user_id} immediately on tab close')
            except Exception as e:
                print(f'Error deleting folder for user {user_id} on tab close: {e}')
        else:
            print(f'Folder does not exist for user {user_id} on tab close')

    return 'OK'

if __name__ == '__main__':
    try:
        app.run(debug=True)
    finally:
        # Set the stop_cleanup_thread event to stop the cleanup thread before exiting
        stop_cleanup_thread.set()
