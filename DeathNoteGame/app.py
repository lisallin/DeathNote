# Import Flask and helper functions for building a web app and APIs
from flask import Flask, render_template, request, jsonify

# Import our GameState class which holds the current state
from game_state import GameState

# Import our core logic function that processes each user step
from logic import run_step

# Create the Flask application object
app = Flask(__name__)

# Create a single global GameState instance to track the current session state
game_state = GameState()


@app.route("/")
def index():
    """
    This function handles GET requests to the root URL ("/").
    It returns the HTML page for the main interface.
    """
    # render_template looks in the 'templates' folder and returns index.html
    return render_template("index.html")


@app.route("/api/reset", methods=["POST"])
def reset():
    """
    This endpoint resets the global game/system state.
    It is called when the user clicks the "Reset" button in the UI.
    """
    global game_state  # Tell Python we want to use the global variable, not a new local one

    # Create a fresh GameState object (all values go back to defaults)
    game_state = GameState()

    # Return a small JSON response saying reset worked
    return jsonify({"status": "ok", "message": "State reset."})


@app.route("/api/step", methods=["POST"])
def step():
    """
    This endpoint handles one interaction step.
    The front end sends user_input (text).
    We send it to run_step, get back a response and updated state,
    then return that as JSON.
    """
    global game_state  # Use the global game_state so it persists across requests

    # Get JSON data from the request body (or use empty dict if there's none)
    data = request.get_json() or {}

    # Extract the 'user_input' field, default to empty string if missing, then strip spaces
    user_input = (data.get("user_input") or "").strip()

    # If the user didn't type anything, return an error JSON with status 400
    if not user_input:
        return jsonify({"error": "No input provided."}), 400

    # Call our core logic function with the current state and user input
    # It returns an updated state and a system_output string to show the user
    game_state, system_output = run_step(game_state, user_input)

    # Return the system_output and a dictionary version of the state as JSON
    return jsonify({
        "system_output": system_output,
        "state": game_state.to_dict()
    })


# This block only runs if we execute this file directly (e.g., python app.py)
if __name__ == "__main__":
    # Start the Flask development server with debug mode on (auto reload + error pages)
    app.run(debug=True)
