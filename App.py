from flask import Flask, render_template, request, session, redirect, url_for, send_file
from Utils import TrainingSession, TrainingSessionUtils  # Adjust this import based on your project structure
import os
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Ensure the uploads directory exists
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Save uploaded file
        file = request.files['file']
        file_path = os.path.join('uploads', file.filename)
        file.save(file_path)

        # Process file to create session_list
        session_list = TrainingSessionUtils.makeSessions(file_path)
        session_list = [TrainingSession.to_dict(i) for i in session_list]
        session['session_list'] = session_list  # Store session_list in session

        # Set a flag indicating a successful upload
        return render_template('index.html', session_list_available=True, file_uploaded=True)

    return render_template('index.html', session_list_available=False, file_uploaded=False)

@app.route('/visualize-options')
def visualize_options():
    # Ensure session_list is available
    if 'session_list' not in session:
        return redirect(url_for('upload_file'))

    return render_template('index.html', session_list_available=True)

@app.route('/visualize', methods=['POST'])
def visualize():
    session_list = session.get('session_list')
    if not session_list:
        return "Session list not found", 400
    # Convert back to TrainingSession objects
    session_list = [TrainingSession.from_dict(d) for d in session_list]
    # Get selected visualization option
    visualization_type = request.form['visualization']
    if visualization_type == 'volume_per_week':
        plot_path = TrainingSessionUtils.visualizeVolumeByWeek(session_list)
    elif visualization_type == 'distance_over_time':
        weight = int(request.form['weight'])
        plot_path = TrainingSessionUtils.visualizeDistanceByTime(session_list, weight)
    elif visualization_type == 'personal_bests':  # New case for Personal Bests
        plot_path = TrainingSessionUtils.visualizePersonalBests()
    else:
        return "Invalid visualization type", 400

    return render_template('visualizations.html', plot_path=plot_path)

if __name__ == '__main__':
    app.run(debug=True)
